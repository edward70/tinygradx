from __future__ import annotations
from typing import TYPE_CHECKING, Union, Type, Tuple, Any, List, Dict, Callable
import functools
from enum import Enum, auto
from tinygrad.helpers import prod, DType, least_upper_dtype
from tinygrad.shape.symbolic import Variable
from dataclasses import dataclass

# these are the llops your accelerator must implement, along with toCpu
# the Enum class doesn't work with mypy, this is static. sorry it's ugly
# NOTE: MOD, CMPLT don't have to be implemented on vectors, just scalars
# NOTE: rdna3 only has RECIP and not DIV. DIV and POW are on the chopping block
class UnaryOps(Enum): EXP2 = auto(); LOG2 = auto(); CAST = auto(); SIN = auto(); SQRT = auto(); RECIP = auto(); NEG = auto() # noqa: E702
class BinaryOps(Enum): ADD = auto(); SUB = auto(); MUL = auto(); DIV = auto(); MAX = auto(); MOD = auto(); CMPLT = auto(); XOR = auto() # noqa: E702
class TernaryOps(Enum): MULACC = auto(); WHERE = auto() # noqa: E702
class ReduceOps(Enum): SUM = auto(); MAX = auto() # noqa: E702
class BufferOps(Enum): LOAD = auto(); CONST = auto(); STORE = auto() # noqa: E702
# Ops below this line are not allowed in ASTs
class MovementOps(Enum): RESHAPE = auto(); PERMUTE = auto(); EXPAND = auto(); PAD = auto(); SHRINK = auto(); STRIDE = auto(); AS_STRIDED = auto() # noqa: E702
class LoadOps(Enum): EMPTY = auto(); CONST = auto(); COPY = auto(); CONTIGUOUS = auto(); CUSTOM = auto() # noqa: E702

Op = Union[UnaryOps, BinaryOps, ReduceOps, MovementOps, LoadOps, TernaryOps, BufferOps]
OpType = Union[Type[UnaryOps], Type[BinaryOps], Type[ReduceOps], Type[MovementOps], Type[LoadOps], Type[TernaryOps], Type[BufferOps]]

if TYPE_CHECKING:
  from tinygrad.shape.shapetracker import ShapeTracker
  from tinygrad.lazy import LazyBuffer

@dataclass(frozen=True)
class MemBuffer:
  idx: int
  dtype: DType
  st: ShapeTracker

@dataclass(frozen=True)
class ConstBuffer:
  val: Union[int, float]
  dtype: DType
  st: ShapeTracker

@dataclass(frozen=True)
class ScheduleItem:
  ast: LazyOp
  out: LazyBuffer
  inputs: Tuple[LazyBuffer, ...]
  var_vals: Dict[Variable, int]

@dataclass(frozen=True)
class LazyOp:
  op: Op
  src: Tuple[LazyOp, ...] = ()
  arg: Any = None
  def __repr__(self): return f"LazyOp(op={self.op}, src={self.src}, arg={self.arg})"
  @functools.cached_property
  def hash(self): return hash((self.op, self.src, self.arg))
  def __hash__(self): return self.hash
  def get_lazyops(self) -> List[LazyOp]: return [self] + [item for x in self.src for item in x.get_lazyops()]

def vars_from_ast(ast:LazyOp) -> List[Variable]:
  return sorted(set.union(*[x.arg.st.vars() for x in ast.get_lazyops() if x.op in BufferOps], set()), key=lambda x: str(x.expr))

# **************** independent FlopCounter ****************

@dataclass
class FlopCounter:
  shape: Tuple[int, ...]
  dtype: DType
  flops: int
  mem: Dict[int, int]
  @property
  def mem_estimate(self): return sum(self.mem.values())
  def consume_flops(self):
    self.flops, ret = 0, self.flops
    return ret

InterpretedFlopCounter: Dict[Op, Callable] = {
  BufferOps.LOAD: lambda arg: FlopCounter(arg.st.shape, arg.dtype, 0, {arg.idx: arg.dtype.itemsize*arg.st.size()}),
  BufferOps.CONST: lambda arg: FlopCounter(arg.st.shape, arg.dtype, 0, {}),
  BufferOps.STORE: lambda self,arg: FlopCounter(arg.st.shape, arg.dtype, self.consume_flops(), {**self.mem, arg.idx: arg.dtype.itemsize*arg.st.size()}),  # noqa: E501
  UnaryOps.CAST: lambda self,arg: FlopCounter(self.shape, arg[0], self.consume_flops(), self.mem),   # cast uses no flops
  **{op:lambda self: FlopCounter(self.shape, self.dtype, self.consume_flops() + prod(self.shape), self.mem) for op in UnaryOps if op != UnaryOps.CAST},  # noqa: E501
  **{op:lambda self,y: FlopCounter(self.shape, least_upper_dtype(self.dtype, y.dtype), self.consume_flops() + y.consume_flops() + prod(self.shape), {**self.mem, **y.mem}) for op in BinaryOps},  # noqa: E501
  **{op:lambda self,new_shape: FlopCounter(new_shape, self.dtype, self.consume_flops() + prod(self.shape), self.mem) for op in ReduceOps},
  TernaryOps.WHERE: lambda self,y,z: FlopCounter(self.shape, least_upper_dtype(y.dtype, z.dtype), self.consume_flops() + y.consume_flops() + z.consume_flops() + prod(self.shape), {**self.mem, **y.mem, **z.mem})}  # noqa: E501

@functools.lru_cache(None)
def get_lazyop_info(ast:LazyOp) -> FlopCounter:
  @functools.lru_cache(None) # NOTE: this cache needs to be recreated for new ASTs
  def run_ast(ast): return InterpretedFlopCounter[ast.op](*([run_ast(x) for x in ast.src]+([ast.arg] if ast.arg is not None else [])))
  return run_ast(ast)
