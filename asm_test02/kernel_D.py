"""FlyDSL arithmetic traced at build time into a callable device function."""
import flydsl.expr as fx


def kernel_D(value: fx.Uint32, multiplier: fx.Uint32) -> fx.Uint32:
    return value * multiplier + fx.Uint32(11)
