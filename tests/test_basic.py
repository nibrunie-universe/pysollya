"""Basic tests for pysollya."""
import pysollya
from pysollya import *


def test_import():
    assert hasattr(pysollya, "x")
    assert hasattr(pysollya, "sin")
    assert hasattr(pysollya, "remez")


def test_parse():
    r = S("1 + 2")
    assert float(r) == 3.0


def test_interval():
    iv = Interval(-1, 1)
    assert repr(iv) == "[-1;1]"


def test_arithmetic():
    a, b = S("3"), S("5")
    assert float(a + b) == 8.0
    assert float(a * b) == 15.0
    assert float(a - b) == -2.0
    assert float(a / b) == 0.6
    assert float(a ** S("2")) == 9.0


def test_mixed_int_arithmetic():
    a = int(3)
    b = S("5")
    assert float(a + b) == 8.0
    assert float(a * b) == 15.0
    assert float(a - b) == -2.0
    assert float(a / b) == 0.6
    assert float(a ** b) == 243.0
    assert float(b + a) == 8.0
    assert float(b * a) == 15.0
    assert float(b - a) == 2.0
    assert float(b / a) == 5.0 / 3.0
    assert float(b ** a) == 125.0


def test_mixed_float_arithmetic():
    a = float(3)
    b = S("5")
    assert float(a + b) == 8.0
    assert float(a * b) == 15.0
    assert float(a - b) == -2.0
    assert float(a / b) == 0.6
    assert float(a ** b) == 243.0
    assert float(b + a) == 8.0
    assert float(b * a) == 15.0
    assert float(b - a) == 2.0
    assert float(b / a) == 5.0 / 3.0
    assert float(b ** a) == 125.0


def test_math_functions():
    f = sin(x)
    assert "sin" in repr(f)
    g = exp(x) + cos(x)
    assert "exp" in repr(g)
    assert "cos" in repr(g)


def test_polynomial_ops():
    p = x ** 3 + S("2") * x ** 2 + S("3") * x + S("4")
    assert int(degree(p)) == 3
    h = horner(p)
    assert repr(h)  # non-empty
    d = diff(p)
    assert repr(d)


def test_remez():
    f = sin(x) / x
    iv = Interval(-1, 1)
    p = remez(f, 5, iv)
    assert int(degree(p)) == 5
    err = infnorm(f - p, iv)
    assert repr(err)


def test_taylor():
    t = taylor(sin(x), 5, S("0"))
    assert repr(t)


def test_settings():
    old = get_prec()
    set_prec(S("200"))
    assert int(get_prec()) == 200
    set_prec(old)


def test_constants():
    assert repr(pi) == "pi"
    assert repr(on)
    assert repr(off)


def test_fpminimax_double():
    """fpminimax with uniform double-precision coefficients."""
    f = sin(x) / x
    iv = Interval(-1, 1)
    deg = 4
    formats = [doubleformat] * (deg + 1)
    p = fpminimax(f, deg, formats, iv)
    assert int(degree(p)) == deg
    # Check the result is a valid polynomial that approximates f
    err = infnorm(f - p, iv)
    assert float(sup(err)) < 1e-2


def test_fpminimax_single():
    """fpminimax with uniform single-precision coefficients."""
    f = exp(x)
    iv = Interval(S("-0.5"), S("0.5"))
    deg = 3
    formats = [singleformat] * (deg + 1)
    p = fpminimax(f, deg, formats, iv)
    assert int(degree(p)) == deg
    err = infnorm(f - p, iv)
    # single precision is ~2^-24 ≈ 6e-8, degree 3 won't reach that
    assert float(sup(err)) < 1e-2


def test_fpminimax_mixed_formats():
    """fpminimax with mixed double/single coefficient formats."""
    f = cos(x)
    iv = Interval(S("-0.5"), S("0.5"))
    deg = 4
    # Even coefficients in double, odd in single
    formats = [doubleformat if i % 2 == 0 else singleformat for i in range(deg + 1)]
    p = fpminimax(f, deg, formats, iv)
    assert int(degree(p)) == deg


def test_fpminimax_vs_remez():
    """fpminimax error should be close to (but not better than) remez."""
    f = sin(x) / x
    iv = Interval(-1, 1)
    deg = 5
    p_remez = remez(f, deg, iv)
    p_fpm = fpminimax(f, deg, [doubleformat] * (deg + 1), iv)
    err_remez = float(sup(infnorm(f - p_remez, iv)))
    err_fpm = float(sup(infnorm(f - p_fpm, iv)))
    # fpminimax with rounded coefficients can't beat remez
    assert err_fpm >= err_remez * 0.9  # allow small numerical margin
    # but should still be a reasonable approximation (within 100x)
    assert err_fpm < err_remez * 100


def test_display():
    a = S("0x1.8p-1")
    assert float(a) == 0.75
    save_display = get_display()
    set_display(hexadecimal)
    assert str(a) == "0x1.8p-1"
    set_display(dyadic)
    assert str(a) == "3b-2"
    set_display(default)
    assert str(a) == "0.75"
    set_display(save_display)



if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS: {name}")
    print("All tests passed!")

