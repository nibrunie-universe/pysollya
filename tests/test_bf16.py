"""Tests for BFloat16 precision support in pysollya."""
import pysollya
from pysollya import *


def test_bfloat16_import():
    """bfloat16_sol and bfloat16format should be importable."""
    assert hasattr(pysollya, "bfloat16_sol")
    assert hasattr(pysollya, "bfloat16format")


def test_bfloat16_sol_exact_value():
    """Rounding an exactly-representable BF16 value should be a no-op."""
    # 1.0 is exactly representable in any IEEE-like format
    result = bfloat16_sol(S("1"))
    assert float(result) == 1.0

    # 2.0, -2.0 also exact
    assert float(bfloat16_sol(S("2"))) == 2.0
    assert float(bfloat16_sol(S("-2"))) == -2.0

    # 0.0 is exact
    assert float(bfloat16_sol(S("0"))) == 0.0


def test_bfloat16_sol_rounding():
    """Rounding a value that is not exactly representable in BF16.

    BFloat16: 1 sign + 8 exponent + 7 significand (8 bits of precision).
    3.14 should round to the nearest BF16 value.
    The BF16 representable values near 3.14 are:
      3.125  = 1.1001 * 2^1   (exact in 8 bits)
      3.15625 = 1.10010_1 * 2^1  (exact in 8 bits)
    3.14 is closer to 3.140625 (1.1001001 * 2^1) — which is exact in 8 bits.
    """
    result = bfloat16_sol(S("3.14"))
    val = float(result)
    # Should be a BF16-representable value near 3.14
    assert abs(val - 3.14) < 0.05


def test_bfloat16_sol_one_third():
    """1/3 rounded to BF16: 8 bits of significand precision.

    1/3 ≈ 0.333... The nearest BF16 value is 0.33203125 = 1.0101010 * 2^{-2}.
    """
    result = bfloat16_sol(S("1") / S("3"))
    val = float(result)
    assert abs(val - 1.0 / 3.0) < 0.01


def test_bfloat16format_object():
    """bfloat16format should be a valid Sollya object with a repr."""
    r = repr(bfloat16format)
    assert r  # non-empty


def test_bfloat16_function_composition():
    """bfloat16_sol should work as part of a function expression."""
    f = bfloat16_sol(x)
    assert repr(f)  # should produce a valid repr string
    # Evaluate at a point
    val = float(f(S("1.5")))
    assert val == 1.5  # 1.5 is exact in BF16


def test_bfloat16_fpminimax():
    """fpminimax with uniform BFloat16 coefficients."""
    f = exp(x)
    iv = Interval(S("-0.5"), S("0.5"))
    deg = 3
    formats = [bfloat16format] * (deg + 1)
    p = fpminimax(f, deg, formats, iv)
    assert int(degree(p)) == deg
    err = infnorm(f - p, iv)
    # BF16 has only ~8 bits of precision, so error will be larger than single
    assert float(sup(err)) < 1.0


def test_bfloat16_fpminimax_mixed():
    """fpminimax with mixed BFloat16 and single-precision coefficients."""
    f = cos(x)
    iv = Interval(S("-0.5"), S("0.5"))
    deg = 4
    # Even coefficients in BF16, odd in single
    formats = [bfloat16format if i % 2 == 0 else singleformat for i in range(deg + 1)]
    p = fpminimax(f, deg, formats, iv)
    assert int(degree(p)) == deg


def test_bfloat16_vs_single_precision():
    """BFloat16 rounding should lose more precision than single rounding."""
    val = S("3.14159265358979")
    bf16_val = float(bfloat16_sol(val))
    sg_val = float(single_sol(val))
    # Single has 24 bits, BF16 has 8 bits: single should be closer to the original
    original = 3.14159265358979
    assert abs(sg_val - original) <= abs(bf16_val - original)


def test_bfloat16_large_value():
    """BFloat16 should handle large values (shared exponent range with float32)."""
    result = bfloat16_sol(S("256"))
    assert float(result) == 256.0

    result = bfloat16_sol(S("1024"))
    assert float(result) == 1024.0


def test_bfloat16_small_value():
    """BFloat16 should handle small (subnormal-ish) values."""
    result = bfloat16_sol(S("0.0078125"))  # 2^-7, exact
    assert float(result) == 0.0078125
    smallest_subnormal = S("0x0.02p-126")
    result = bfloat16_sol(smallest_subnormal) # smallest subnormal value
    assert float(result) == smallest_subnormal
    underflow_value = S("0x0.01p-126")
    result = bfloat16_sol(underflow_value) # smallest subnormal value
    assert float(result) != underflow_value


def test_bfloat16_display():
    save_display = get_display()
    a = S("0x1.08p-126")
    assert bfloat16_sol(a) == a
    set_display(hexadecimal)
    assert  str(bfloat16_sol(a)) == "0x1.08p-126"
    set_display(save_display)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS: {name}")
    print("All tests passed!")
