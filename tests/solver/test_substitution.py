"""Substituting nothing into a quantifier returns the quantifier, not a copy of it.

The walk rebuilds a quantifier when its body or its patterns changed. It decided
that by comparing the freshly built list of patterns against the stored tuple of
them -- and in Python a list is never equal to a tuple, however their contents
match. So the test was true on every pass and every quantifier the walk touched
was rebuilt, substitution or none.

Hash-consing hid the cost: rebuilding returns the identical cached object, so
nothing observable was wrong. That is exactly why it needed a type checker to
find, and why it needs a test now that it is fixed.
"""

from endoxa.solver import BOOL_SORT, USort
from endoxa.solver.ast.context import global_ctx
from endoxa.solver.ast.expr import FuncDecl
from endoxa.solver.ast.utils import substitute

U = USort("U")


def _forall_p_of_x_with_pattern():
    """``![X]: p(X)``, patterned on ``p(X)`` -- a quantifier that carries patterns."""
    x = global_ctx.mk_bound_var("X", U)
    p_of_x = global_ctx.mk_app(FuncDecl("p", (U,), BOOL_SORT), x)
    return global_ctx.mk_quantifier(
        is_forall=True,
        bound_vars=(x,),
        body=p_of_x,
        patterns=(global_ctx.mk_pattern(p_of_x),),
    )


def test_a_substitution_that_touches_nothing_does_not_rebuild(monkeypatch):
    """Asserted as "the rebuild does not happen", because the result cannot show it.

    Hash-consing returns the identical object for identical arguments, so an
    identity check on the result passes whether or not the quantifier was rebuilt
    -- it passes on the broken comparison too, and pins nothing. The call is the
    only place the difference is visible.
    """
    quantifier = _forall_p_of_x_with_pattern()
    # A binding for a variable the quantifier does not mention: non-empty, so the
    # walk descends, and irrelevant, so it should find nothing to change.
    theta = {global_ctx.mk_bound_var("Y", U): global_ctx.mk_app(FuncDecl("c", (), U))}

    rebuilds = []
    real = global_ctx.mk_quantifier
    monkeypatch.setattr(
        global_ctx,
        "mk_quantifier",
        lambda **kwargs: (rebuilds.append(kwargs), real(**kwargs))[1],
    )

    assert substitute(quantifier, theta) is quantifier
    assert rebuilds == []


def test_a_substitution_that_does_touch_it_still_rebuilds():
    """The control: the unchanged path must not be reached by skipping the work."""
    x = global_ctx.mk_bound_var("X", U)
    y = global_ctx.mk_bound_var("Y", U)
    q_decl = FuncDecl("q", (U, U), BOOL_SORT)
    quantifier = global_ctx.mk_quantifier(
        is_forall=True,
        bound_vars=(x,),
        body=global_ctx.mk_app(q_decl, x, y),
        patterns=(),
    )

    substituted = substitute(quantifier, {y: global_ctx.mk_app(FuncDecl("c", (), U))})

    assert substituted is not quantifier
    assert "Y" not in str(substituted)
