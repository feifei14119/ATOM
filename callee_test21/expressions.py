"""Pure FlyDSL functions traced at build time; no GPU launcher or inline asm."""
import flydsl.expr as fx


def mul_add(a: fx.Float32, b: fx.Float32) -> fx.Float32:
    return a + b * a
