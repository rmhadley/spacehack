"""AST transformer for the ``spacehack`` GameContext modal migration.

Rewrites :mod:`spacehack.__main__` so every modal ``_run_X`` + ``render_X``
+ call site in ``_run_game`` closes over a single ``ctx: GameContext``,
instead of 3-5 loose ``context`` / ``log`` / ``stats`` / ``owned_ship``
/ ``active`` parameters. After the rewrite, adding a new GameContext
field is a one-spot edit on the
:class:`~spacehack.game_context.GameContext` dataclass instead of
threading through 3 call layers in :mod:`~spacehack.__main__`.

**Why an AST transformer?** Hand-typed text substitution for a ~3800-
line file with 11 similar-but-distinct modal patterns is fragile --
multi-line ``str.replace`` calls are a string-match lottery that's
silently broken by one stray whitespace change. AST rewriting is
*verifiable*: the test asserts structural properties (signatures
correctly filtered, dropped params absent from bodies, ``ctx``
replaces ``context``) rather than byte-exact formatting.

**Usage**::

    from tools.migrate_modal_to_ctx import migrate_source
    new_src = migrate_source(open('src/spacehack/__main__.py').read())

**What this transformer does and does NOT do**:

* DOES target the 11 ``_run_X`` functions + their ``render_X``
  counterparts. ``_run_game`` is handled as a CALL_SITE_CONTAINER --
  its body is rewritten (call sites use ``ctx``, loose args dropped)
  but its OWN signature is left alone because it still receives a
  raw ``tcod.context.Context`` from :func:`run`. Constructing the
  ``ctx = GameContext(context, ...)`` line inside :func:`_run_game`
  is P3.6.1 manual work -- the transformer assumes :func:`_run_game`
  ``ctx`` references inside its body will resolve once that line is
  added.
* DOES NOT touch helpers like :func:`_jump_to_system`,
  :func:`_launch_to_space`, :func:`_return_to_city`,
  :func:`_handle_combat_encounter`, :func:`_detect_combat_encounter`.
  They still take ``log`` / ``game_map`` / ``player`` as ordinary
  params; the GameContext migration for those is a separate, simpler
  commit.
* DOES NOT add ``ctx.X = X`` mutation mirrors in :func:`_run_game`;
  those are P3.6.2 (added BEFORE the actual modal migration so
  rewrites land on an already-mirror-redundant code base).
* DOES NOT inject ``from .game_context import GameContext`` into
  the rewritten file. The transformer synthesizes ``ctx:
  GameContext`` annotations on every ``render_X`` signature, so
  the target file MUST already have that import resolvable at
  module load. Add the import line before applying the transformer,
  or inject it programmatically in the P3.6.1 commit body (~1 line
  before the first render_X).
"""
from __future__ import annotations

import ast
from typing import Set


# Local parameter names that map 1:1 onto a :class:`GameContext`
# field value (or, for ``owned`` / ``active``, onto an aliased
# field). These are dropped from ``_run_X`` + ``render_X``
# signatures and their body references rewritten to ``ctx.<value>``.
PARAM_MAPPING: dict[str, str] = {
    "log": "log",
    "stats": "stats",
    "owned_ship": "player_owned_ship",   # MIGRATION GOTCHA
    "owned": "player_owned_ship",        # RENAMED: most modals say ``owned``
    "active": "player_active_mission",   # ALIAS: quest_log param is ``active``
    "character_info": "character_info",
    "game_map": "game_map",
}
# Above list deliberately OMITS ``context`` (renamed, not dropped)
# and modal-specific locals (ship_pos, jp, npc, planet_obj, blocker,
# ship, menu, species_id, class_id, deliver_mission, missions,
# active_mission_text) -- those stay in the signature.

# Derived set for cross-modal call-site rewriting: an arg is treated
# as ``a loose param that the target modal will already access via
# ctx`` if its NAME is EITHER a PARAM_MAPPING key (e.g. ``log``,
# ``stats``, ``active``, ``owned_ship``, ``owned``) OR a value
# (e.g. ``player_active_mission`` -- the renamed alias of ``active``;
# ``player_owned_ship`` -- renamed alias of ``owned_ship``). The
# visual playtest surfaced both shapes leaking past the previous
# ``arg.id in PARAM_MAPPING`` check; the value shape is exactly
# what P3.6.1b's Hand-Fixes 15-17 patched by hand. This derived set
# closes the gap at the transformer source so those hand-fixes
# become obsolete.
LOOSE_ARG_NAMES: frozenset[str] = frozenset(PARAM_MAPPING) | frozenset(PARAM_MAPPING.values())

# Attribute access from ``ctx`` whose .attr name is one of the
# droppable loose-arg VALUES. We treat ``ctx.player_active_mission``,
# ``ctx.player_owned_ship``, ``ctx.log``, ``ctx.stats``,
# ``ctx.character_info``, ``ctx.game_map`` at a call site as a
# redundant pass-through -- the target modal already takes ``ctx``
# and reads it internally. The previous migrator only handled
# ``ast.Name`` nodes; ``ast.Attribute`` nodes passed through
# unchanged, surfacing Hand-Fix 17 in P3.6.1b for ``_run_ship_view``.
CTX_LOOSE_ATTR_DROP: frozenset[str] = frozenset(PARAM_MAPPING.values())

# Functions whose SIGNATURE + BODY are rewritten. Strict positive
# allowlist; everything else (helpers like _jump_to_system, the
# creation-screen choose_species dispatchers not named below, etc.)
# is untouched. Mapping between _run_X and render_X is implicit --
# they're each in the set if they need rewriting.
TARGET_FUNCTIONS: frozenset[str] = frozenset({
    # Per-creation-screen modals.
    "_run_pick", "_run_confirm",
    # Space-mode modals.
    "_run_navigation", "_run_goto", "_run_jump_menu", "_run_planet_menu",
    "_run_ship_buy", "_run_npc_talk",
    "_run_mission_offerings", "_run_quest_log",
    "_run_ship_menu", "_run_ship_view",
    # Corresponding render functions.
    "render_navigation", "render_jump_menu", "render_planet_menu",
    "render_ship_buy", "render_npc_talk",
    "render_mission_offerings", "render_quest_log",
    "render_ship_menu", "render_ship_view",
})

# Functions whose SIGNATURE is NOT migrated but whose BODY is
# visited so any call site to a TARGET_FUNCTIONS callee gets its
# loose args dropped + ``context`` renamed to ``ctx``. ``_run_game``
# is in this set because it still receives ``tcod.context.Context``
# from :func:`run`; constructing ``ctx = GameContext(context, ...)``
# inside its body is a manual P3.6.1 step (out of scope for this
# transformer).
CALL_SITE_CONTAINERS: frozenset[str] = frozenset({"_run_game"})


class ContextTransformer(ast.NodeTransformer):
    """Mechanically rewrite modal ``_run_X`` + ``render_X`` + call sites.

    Algorithm (runs on each :class:`ast.FunctionDef` in
    :func:`migrate_source`):

    1.  If ``node.name`` is in :data:`TARGET_FUNCTIONS`, rewrite
        the signature: rename ``context`` -> ``ctx`` (dropping
        the annotation on the renamed arg so the generated source
        reads ``ctx,`` rather than ``ctx: tcod.context.Context``,
        which has been visibly jarring in earlier iterations) and
        drop every parameter whose name is in
        :data:`PARAM_MAPPING` keys. Both positional
        (``node.args.args``) and keyword-only
        (``node.args.kwonlyargs``) blocks are filtered; their
        associated defaults arrays are filtered in lockstep to
        keep Python's "trailing defaults" invariant. Positional
        defaults are emitted untouched under the caveat that
        spacehack's current modal set has none on dropped fields
        -- see :attr:`__doc__` note.

    2.  Walk the function body. References inside TARGET_FUNCTIONS
        get rewritten by :meth:`visit_Name` (loose-param load -> 
        ``ctx.<mapped>``; ``context`` load -> ``ctx``) and by
        :meth:`visit_Call` (Modal API + cross-modal call sites).

    3.  If we are inside a :data:`CALL_SITE_CONTAINERS` definition
        (e.g. :func:`_run_game`), the signature is left alone but
        the body's call sites are still rewritten (loose args
        dropped, ``context`` -> ``ctx``).

    The transformer is intentionally *stateless across functions* --
    the only cross-node state is ``self.current_function`` (which
    function we're currently walking) and ``self.dropped_params``
    (the set of params dropped from the current function's
    signature). This makes it safe to run once over the whole file
    in declaration order.
    """

    def __init__(self) -> None:
        super().__init__()
        # Stack of currently-open function names. ``current_function``
        # returns the topmost (= innermost) name. Nested defs push and
        # pop on entry/exit so references between nested defs in the
        # same TARGET_FUNCTION body still see the TARGET's name as
        # ``current_function`` (which gates the context -> ctx
        # rename in ``visit_Name``). Without the stack, resetting to
        # None after each FunctionDef visit silently broke Modal API
        # rewrites that came AFTER a nested def (e.g. the
        # ``ui.Modal(context, console).run(...)`` call after the
        # ``def _render()`` closure inside ``_run_navigation``).
        self._function_stack: list[str | None] = []
        self.dropped_params: Set[str] = set()

    @property
    def current_function(self) -> str | None:
        return self._function_stack[-1] if self._function_stack else None

    # ----------------------------------------------------------------
    # Signature rewriting
    # ----------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Rewrite signature if name in :data:`TARGET_FUNCTIONS`.

        Uses a stack-based ``current_function`` so nested defs
        (e.g. ``_render`` closures inside ``_run_X``) push/pop
        their name WITHOUT clearing the OUTER target function's
        name. References in the outer target's body that come
        AFTER a nested def still see ``current_function`` as the
        outer target, so :meth:`visit_Name`'s ``context`` -> 
        ``ctx`` rename fires on them.
        """
        is_target = node.name in TARGET_FUNCTIONS

        # Save parent's dropped_params so we can restore on exit.
        # For TARGET: _rewrite_signature may have set it; on exit
        # we clear it so the next sibling TARGET starts fresh.
        # For nested non-target defs: we INHERIT the parent's so
        # closure references like ``log`` inside ``_render`` rewrite
        # to ``ctx.log`` (matches the outer target's drops); on exit
        # we restore so the next sibling TARGET starts fresh.
        saved_dropped = self.dropped_params.copy()

        if is_target:
            self._rewrite_signature(node)

        # Push this function's name onto the stack.
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()
        self.dropped_params = saved_dropped
        return node

    def _rewrite_signature(self, node: ast.FunctionDef) -> None:
        """Drop loose params + rename ``context`` -> ``ctx`` + add ``ctx`` to render_X signatures.

        Two signature shapes:

        * :func:`_run_X` family originally took ``(context, ...)``.
          We rename ``context`` -> ``ctx``, drop the
          ``: tcod.context.Context`` annotation (cleaner), and
          drop every param whose name is in :data:`PARAM_MAPPING`.
        * :func:`render_X` family originally took ``(console, ...loose,
          ..., screen_w, screen_h, ...)``. None had a ``context``
          param. We drop every loose param AND insert a fresh
          ``ctx: GameContext`` as the second positional arg
          (right after ``console``).
        """
        # Positional args + their defaults filtered in lockstep so
        # defaults stay trailing-aligned. Vanilla Python rule:
        # ``defaults[j]`` applies to ``args[len(args)-len(defaults)+j]``.
        # If we drop a trailing-defaulted arg (the arg that owns the
        # default), we must drop the matching default; otherwise the
        # default silently slides onto the wrong arg.
        old_args_list = list(node.args.args)
        old_defaults_list = list(node.args.defaults)
        new_pos_args_list: list[ast.arg] = []
        kept_indices: list[int] = []
        for i, arg in enumerate(old_args_list):
            if arg.arg == "context":
                arg.arg = "ctx"
                arg.annotation = None
                new_pos_args_list.append(arg)
                kept_indices.append(i)
            elif arg.arg in PARAM_MAPPING:
                self.dropped_params.add(arg.arg)
                # do NOT keep; defaults for this arg (if any) will be
                # filtered out below.
            else:
                new_pos_args_list.append(arg)
                kept_indices.append(i)

        # Rebuild defaults in lockstep with filtered args: a default
        # at position j applies to the arg at old index
        # (len(old_args) - len(old_defaults) + j). If that arg was
        # dropped, the default is dangling -- drop it.
        new_defaults_list: list[ast.expr | None] = []
        if old_defaults_list:
            default_zone_start = len(old_args_list) - len(old_defaults_list)
            for j, default in enumerate(old_defaults_list):
                owner_index = default_zone_start + j
                if owner_index in kept_indices:
                    new_defaults_list.append(default)
                # else: dangling default; drop it
        node.args.args = new_pos_args_list
        node.args.defaults = new_defaults_list

        # render_X functions: if ``ctx`` is not in the (renamed) args,
        # it never had ``context`` to rename, so we add it now as
        # the second positional arg. Detect by checking if any arg
        # in the (post-rename) positional list is named ``ctx``;
        # if not, this is a render_X and we synthesize the param.
        is_render = node.name.startswith("render_")
        has_ctx = any(a.arg == "ctx" for a in new_pos_args_list)
        if is_render and not has_ctx:
            ctx_arg = ast.arg(
                arg="ctx",
                annotation=ast.Name(id="GameContext", ctx=ast.Load()),
            )
            # Insert right after ``console`` (which is always the
            # first positional arg of every render_X).
            insert_at = 1 if (new_pos_args_list and new_pos_args_list[0].arg == "console") else 0
            node.args.args = (
                new_pos_args_list[:insert_at]
                + [ctx_arg]
                + new_pos_args_list[insert_at:]
            )
            # Defaults array stays valid: we only INSERTED a new
            # required arg (``ctx: GameContext``) at index 1 (or 0),
            # shifting positional defaults farther from the tail by
            # one slot. The trailing-defaults invariant (``defaults[j]``
            # applies to the last ``len(defaults)`` args) is not
            # broken by an INSERTION because we inserted a NO-default
            # required arg before the default zone -- except this
            # changes the alignment. Concretely: if old was
            # ``(a, b, c=None)`` and we insert ``ctx`` after ``a``,
            # the new layout is ``(a, ctx, b, c=None)`` -- still
            # valid (c is still trailing-defaulted). If old was
            # ``(a=None,)`` and we insert after ``a``, new is
            # ``(a, ctx=None)`` which silently gives ``ctx`` a
            # default. No current render_X has a positional default,
            # so this is a known limitation flagged for future
            # contributors.

        # Keyword-only args (incl. their defaulted-position table).
        new_kwonly: list[ast.arg] = []
        new_kw_defaults: list[ast.expr | None] = []
        for kwarg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if kwarg.arg in PARAM_MAPPING:
                self.dropped_params.add(kwarg.arg)
            else:
                new_kwonly.append(kwarg)
                new_kw_defaults.append(default)
        node.args.kwonlyargs = new_kwonly
        node.args.kw_defaults = new_kw_defaults

    # ----------------------------------------------------------------
    # Body reference rewriting
    # ----------------------------------------------------------------

    def _is_in_target_scope(self) -> bool:
        """True iff any function on the call stack is in :data:`TARGET_FUNCTIONS`.

        Scans the whole stack rather than only the top so that
        closure bodies (e.g. ``_render`` inside ``_run_ship_buy``)
        still inherit the OUTER target's rewrite rules. A naive
        ``current_function in TARGETS`` check would skip the
        rewrite inside the nested def -- which is exactly the
        bug the stack-based track was meant to fix.
        """
        return any(fn in TARGET_FUNCTIONS for fn in self._function_stack)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        """Rewrite ``context`` -> ``ctx`` and dropped params -> ``ctx.X``.

        Scope check uses :meth:`_is_in_target_scope` (stack-scanning)
        so nested closure bodies inside a TARGET_FUNCTION still
        fire the rewrite -- e.g. ``log.add(...)`` inside the
        ``_render`` closure inside ``_run_ship_buy`` becomes
        ``ctx.log.add(...)``.
        """
        if not isinstance(node.ctx, ast.Load):
            return node
        if not self._is_in_target_scope():
            return node
        if node.id == "context":
            # ``context`` has been renamed to ``ctx`` in some
            # enclosing target's signature; any read of ``context``
            # in a body that's effectively inside that target's
            # scope (the closure inherits it) is a stale reference.
            # Rewrite to ``ctx``.
            node.id = "ctx"
            return node
        if node.id in self.dropped_params and node.id in PARAM_MAPPING:
            return ast.Attribute(
                value=ast.Name(id="ctx", ctx=ast.Load()),
                attr=PARAM_MAPPING[node.id],
                ctx=ast.Load(),
            )
        return node

    # ----------------------------------------------------------------
    # Call-site rewriting
    # ----------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Rewrite Modal API instantiation + cross-modal call sites.

        Two passes:

        * Modal API: ``ui.Modal(ctx, console).run(...)`` becomes
          ``ui.Modal(ctx.context, console).run(...)`` because the
          Modal signature still takes ``tcod.context.Context``
          (P3.6.1 keeps that contract; future P3.x can compress to
          ``Modal(ctx)``).
        * Cross-modal call sites: any call to a name in
          :data:`TARGET_FUNCTIONS` (the 11 modal invocations from
          :func:`_run_game`, or cross-references between modals
          such as :func:`_run_ship_menu` calling
          :func:`_run_ship_view`) gets ``context`` -> ``ctx`` AND
          loose args dropped.
        """
        self.generic_visit(node)

        # ---- ui.Modal API rewrite ----
        # After visit_Name renamed ``context`` -> ``ctx``, the call
        # ``ui.Modal(ctx, console).run(...)`` has its first arg as
        # a bare ``ctx`` Name -- translate to ``ctx.context`` to
        # match Modal's existing signature. Skip if it's already
        # ``ctx.context`` (idempotent rewrite).
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "Modal"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "ctx"
        ):
            node.args[0] = ast.Attribute(
                value=ast.Name(id="ctx", ctx=ast.Load()),
                attr="context",
                ctx=ast.Load(),
            )

        # ---- Cross-modal call-site rewrite ----
        # Resolve callee name robustly: ``Name`` for bare-name calls
        # (``_run_X(...)``), ``Attribute`` for method-style calls
        # (``self._run_X(...)`` or ``ui._run_X(...)``). Both styles
        # are valid Python; the second matters if any future refactor
        # in ``__main__.py`` introduces method-style modal invocation,
        # which would otherwise silently skip the rewrite.
        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee_name = node.func.attr
        else:
            return node
        if callee_name not in TARGET_FUNCTIONS:
            return node
        new_args: list[ast.expr] = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                if arg.id == "context":
                    arg.id = "ctx"  # rename at call site
                    new_args.append(arg)
                elif arg.id in LOOSE_ARG_NAMES:
                    continue  # drop positional loose-arg (key OR value form)
                else:
                    new_args.append(arg)
            elif (
                isinstance(arg, ast.Attribute)
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "ctx"
                and arg.attr in CTX_LOOSE_ATTR_DROP
            ):
                # Drop redundant ``ctx.<loose-arg-value>`` pass-through
                # at cross-modal call sites. The target modal already
                # takes ``ctx`` and reads the field via the same name.
                continue
            else:
                new_args.append(arg)
        node.args = new_args
        new_kwargs: list[ast.keyword] = []
        for kw in node.keywords:
            # Drop loose-arg kwargs BY EITHER KEY (e.g. ``log=log``)
            # OR VALUE form (e.g. ``player_owned_ship=ctx.player_owned_ship``).
            # The positional branch already widens to :data:`LOOSE_ARG_NAMES`;
            # mirror that here so ``_run_X(..., player_owned_ship=ctx.player_owned_ship)``
            # at the call site doesn't leak an orphan kwarg into a signature
            # that has dropped the field. ``kw.arg`` is always a Name string
            # (kwarg keys are syntactically identifiers, not Attribute nodes),
            # so the Attribute-handling logic in the positional loop doesn't
            # apply here.
            if kw.arg is not None and kw.arg in LOOSE_ARG_NAMES:
                continue  # drop kwarg loose-arg (key OR value form)
            new_kwargs.append(kw)
        node.keywords = new_kwargs
        return node


def migrate_source(source: str) -> str:
    """Parse ``source``, run :class:`ContextTransformer`, return rewritten source.

    Post-condition: ``transformer._function_stack == []`` and
    ``transformer.dropped_params == set()``. A non-empty stack
    after the walk means a visit_FunctionDef call forgot to pop
    on exit, which would silently corrupt every subsequent
    migration. Caught here before a multi-file migration uses
    a broken transformer.
    """
    tree = ast.parse(source)
    transformer = ContextTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    assert transformer._function_stack == [], (
        f"_function_stack not empty after visit: {transformer._function_stack}"
    )
    assert transformer.dropped_params == set(), (
        f"dropped_params not empty after visit: {transformer.dropped_params}"
    )
    return ast.unparse(new_tree)


# ===========================================================================
# Round-trip + fingerprint smoke test
# ===========================================================================
# The transformer's output formatting is dictated by ``ast.unparse``,
# which produces one-line defs and inconsistent whitespace -- not
# a target for byte-exact comparison. Instead the test runs the
# transformer on a synthetic input and asserts STRUCTURAL properties:

# 1.  :func:`_run_ship_buy` lost ``stats`` + ``log`` from its
#     positional args (the body-reference rewrite then mapped any
#     ``log`` / ``stats`` Load to ``ctx.log`` / ``ctx.stats``).
# 2.  :func:`render_ship_buy` lost ``stats`` + ``log`` AND gained
#     ``ctx`` as a new positional arg after ``console``.
# 3.  :func:`_run_navigation`'s ``context`` arg is renamed ``ctx``.
# 4.  :func:`_run_game`'s signature is NOT migrated (still has
#     ``context``).
# 5.  ``ui.Modal`` calls inside modal bodies target ``ctx.context``,
#     not ``ctx``.
# 6.  Body references to dropped params (``log``, ``stats``,
#     ``owned``, ``active``, ``character_info``, ``game_map``)
#     become ``ctx.<field>``.
# 7.  Call sites in :func:`_run_game` body lose loose kwargs and
#     rename ``context`` -> ``ctx``.

_TEST_INPUT = '''
def render_ship_buy(console, ship, stats, log, *, screen_width, screen_height):
    """Render the ship-buy dialog."""
    console.clear()
    affordable = stats.gold >= ship.price
    log.add(f"You consider the {ship.name}.")


def _run_ship_buy(
    context: tcod.context.Context,
    ship,
    stats,
    log,
) -> ShipBuyOutcome:
    """Show the ship-buy modal."""
    console = make_console()
    def _render() -> None:
        render_ship_buy(console, ship, stats, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    return ui.Modal(context, console).run(_render, update_ship_buy)


def _run_navigation(
    context: tcod.context.Context,
    ship_pos: world.Position,
) -> NavigationOutcome:
    """Show the system-map overlay."""
    console = make_console()
    def _render() -> None:
        render_navigation(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, ship_pos=ship_pos)
    return ui.Modal(context, console).run(_render, update_navigation)


def _run_game(
    context: tcod.context.Context,
    species_id: str,
    class_id: str,
) -> None:
    outcome = _run_navigation(context, player.pos)
    buy = _run_ship_buy(context, ship, stats=stats, log=log)


def _run_quest_log(
    context: tcod.context.Context,
    active,
) -> QuestLogOutcome:
    """Show the quest log modal."""
    console = make_console()
    def _render() -> None:
        render_quest_log(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    log.add(f"Active: {active.title}")
    return ui.Modal(context, console).run(_render, update_quest_log)


def render_planet_menu(console, planet_obj, *, character_info, stats, screen_width, screen_height):
    """Render the planet menu."""
    console.clear()
    log.add(f"You visit {planet_obj.name}.")


def _run_planet_menu(
    context: tcod.context.Context,
    planet_obj,
    *,
    character_info,
    stats,
    log,
) -> PlanetMenuOutcome:
    """Show the planet menu modal."""
    console = make_console()
    def _render() -> None:
        render_planet_menu(console, planet_obj, character_info=character_info, stats=stats, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    return ui.Modal(context, console).run(_render, update_planet_menu)


def _run_jump_menu(
    context: tcod.context.Context,
    jp,
    target_system_id,
    owned_ship=None,
) -> JumpMenuOutcome:
    """Show the jump menu modal."""
    console = make_console()
    def _render() -> None:
        label = f"{jp.label} to {target_system_id}"
        if owned_ship is None:
            log.add("No owned ship.")
        else:
            log.add(f"You jump {label}.")
    return ui.Modal(context, console).run(_render, update_jump_menu)


def _run_ship_menu(
    context: tcod.context.Context,
) -> ShipMenuOutcome:
    """Show ship menu (delegates to ship view)."""
    return _run_ship_view(context, ship)
'''


def _args_of(func: ast.FunctionDef) -> list[tuple[str, bool]]:
    """Return ``[(arg_name, is_keyword_only), ...]`` for diagnostics."""
    out: list[tuple[str, bool]] = []
    for a in func.args.args:
        out.append((a.arg, False))
    if func.args.vararg:
        out.append(("*" + func.args.vararg.arg, False))
    if func.args.kwonlyargs:
        for a in func.args.kwonlyargs:
            out.append((a.arg, True))
    return out


def _body_has_load_of(tree: ast.AST, func_name: str, name: str) -> bool:
    """True if ``func_name``'s body contains a ``Load`` of bare ``name``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id == name and isinstance(sub.ctx, ast.Load):
                    # Only count Loads INSIDE the body, not the
                    # arg-list itself.
                    if sub not in getattr(node.args, "args", []) + getattr(node.args, "kwonlyargs", []):
                        return True
            return False
    raise KeyError(func_name)


def _calls_in_body(tree: ast.AST, func_name: str) -> list[ast.Call]:
    """Return all :class:`ast.Call` nodes inside ``func_name``'s body."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.FunctionDef) and sub is not node:
                    # Don't recurse into nested defs (they're
                    # closures like the modal render body; we'll
                    # check those separately).
                    continue
                if isinstance(sub, ast.Call):
                    calls.append(sub)
    return calls


def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise KeyError(name)


def smoke_test() -> None:
    """Assert structural invariants on the rewritten output."""
    new_src = migrate_source(_TEST_INPUT)
    tree = ast.parse(new_src)

    # (1) ``_run_ship_buy`` lost ``stats`` + ``log``.
    run_ship_buy = _find_func(tree, "_run_ship_buy")
    arg_names = [a.arg for a in run_ship_buy.args.args]
    assert arg_names == ["ctx", "ship"], (
        f"_run_ship_buy should have positional [ctx, ship] after migration; "
        f"got {arg_names}"
    )

    # (2) ``render_ship_buy`` lost ``stats`` + ``log`` and gained
    # ``ctx`` after ``console``.
    render_ship_buy = _find_func(tree, "render_ship_buy")
    rsb_args = [a.arg for a in render_ship_buy.args.args]
    assert rsb_args == ["console", "ctx", "ship"], (
        f"render_ship_buy should be [console, ctx, ship]; got {rsb_args}"
    )

    # (3) ``_run_navigation``'s ``context`` -> ``ctx``.
    run_nav = _find_func(tree, "_run_navigation")
    nav_args = [a.arg for a in run_nav.args.args]
    assert nav_args == ["ctx", "ship_pos"], (
        f"_run_navigation should have positional [ctx, ship_pos]; "
        f"got {nav_args}"
    )

    # (4) ``_run_game`` signature UNCHANGED.
    run_game = _find_func(tree, "_run_game")
    game_args = [a.arg for a in run_game.args.args]
    assert game_args == ["context", "species_id", "class_id"], (
        f"_run_game signature should be UNCHANGED [context, species_id, class_id]; "
        f"got {game_args}"
    )

    # (5) Modal API rewrite: ``ui.Modal(ctx.context, ...)`` in bodies.
    modal_calls_in_ship_buy = [
        c for c in ast.walk(run_ship_buy)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        and c.func.attr == "Modal"
    ]
    assert len(modal_calls_in_ship_buy) == 1, "expected exactly one ui.Modal call in _run_ship_buy"
    first_arg = modal_calls_in_ship_buy[0].args[0]
    assert (
        isinstance(first_arg, ast.Attribute)
        and isinstance(first_arg.value, ast.Name)
        and first_arg.value.id == "ctx"
        and first_arg.attr == "context"
    ), f"ui.Modal first arg should be ctx.context; got {ast.dump(first_arg)}"

    # (6) Body references to dropped params become ctx.<field>.
    # Inside render_ship_buy, ``log.add(...)`` should be ``ctx.log.add(...)``.
    assert _body_has_load_of(render_ship_buy, "render_ship_buy", "log") is False, (
        "render_ship_buy body should NOT contain a bare `log` Load after migration"
    )
    # And ``stats.gold`` should be ``ctx.stats.gold``.
    # We check by spawning a Name with id='stats' - none should appear in body.
    stats_loads_in_render = [
        n for n in ast.walk(render_ship_buy)
        if isinstance(n, ast.Name) and n.id == "stats" and isinstance(n.ctx, ast.Load)
        # also exclude arg-list defs:
        and n not in render_ship_buy.args.args + render_ship_buy.args.kwonlyargs
    ]
    assert stats_loads_in_render == [], (
        "render_ship_buy body should not have bare `stats` Loads; "
        f"found {len(stats_loads_in_render)}"
    )

    # (7) Call sites in _run_game are rewritten: lose loose
    # kwargs; rename context -> ctx.
    game_calls = _calls_in_body(tree, "_run_game")
    modal_targeted_calls = [
        c for c in game_calls
        if isinstance(c.func, ast.Name) and c.func.id in TARGET_FUNCTIONS
    ]
    # Two calls: _run_navigation + _run_ship_buy.
    assert len(modal_targeted_calls) == 2, (
        f"_run_game should have exactly 2 modal-targeted Calls; "
        f"got names {[c.func.id for c in modal_targeted_calls]}"
    )
    # Both first args should be Name(ctx).
    for c in modal_targeted_calls:
        if c.func.id == "_run_navigation":
            assert isinstance(c.args[0], ast.Name) and c.args[0].id == "ctx", (
                f"_run_navigation call site's first arg should be `ctx`; "
                f"got {ast.dump(c.args[0])}"
            )
            # No more positional args after `(ctx, player.pos)`.
            assert len(c.args) == 2, (
                f"_run_navigation call site should have 2 args; got {len(c.args)}"
            )
        if c.func.id == "_run_ship_buy":
            # Call was `_run_ship_buy(context, ship, stats=stats, log=log)`.
            # After migration: `_run_ship_buy(ctx, ship)` -- stats
            # + log kwargs dropped.
            args_str = [ast.dump(a) for a in c.args]
            kws = [k.arg for k in c.keywords]
            assert len(c.args) == 2, (
                f"_run_ship_buy call site should have 2 args after "
                f"`stats`/`log` kwargs dropped; got {len(c.args)}"
            )
            assert kws == [], (
                f"_run_ship_buy call site should have NO loose kwargs; "
                f"got {kws}"
            )

    # (8) _run_quest_log: alias ``active`` -> ``player_active_mission``.
    quest_log = _find_func(tree, "_run_quest_log")
    ql_args = [a.arg for a in quest_log.args.args]
    assert ql_args == ["ctx"], (
        f"_run_quest_log should have only ctx after `active` dropped; "
        f"got {ql_args}"
    )
    has_alias_access = any(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "ctx"
        and n.attr == "player_active_mission"
        for n in ast.walk(quest_log)
    )
    assert has_alias_access, (
        "_run_quest_log body should contain ``ctx.player_active_mission``"
    )

    # (9) _run_planet_menu: kw-only ``character_info, stats, log`` dropped.
    planet_menu = _find_func(tree, "_run_planet_menu")
    pm_args = [a.arg for a in planet_menu.args.args]
    assert pm_args == ["ctx", "planet_obj"], (
        f"_run_planet_menu should drop kw-only + strip `context`; "
        f"got {pm_args}"
    )
    pm_kwonly = [a.arg for a in planet_menu.args.kwonlyargs]
    assert pm_kwonly == [], (
        f"_run_planet_menu should have NO kw-only args after drop; "
        f"got {pm_kwonly}"
    )

    # (9b) render_planet_menu: kw-only dropped, ctx inserted after console.
    render_planet_menu_node = _find_func(tree, "render_planet_menu")
    rpm_args = [a.arg for a in render_planet_menu_node.args.args]
    rpm_kwonly = [a.arg for a in render_planet_menu_node.args.kwonlyargs]
    assert rpm_args == ["console", "ctx", "planet_obj"], (
        f"render_planet_menu should be [console, ctx, planet_obj]; "
        f"got pos={rpm_args}, kwonly={_args_of(render_planet_menu_node)}"
    )
    assert rpm_kwonly == ["screen_width", "screen_height"], (
        f"render_planet_menu should keep non-loose kw-only; "
        f"got {rpm_kwonly}"
    )

    # (10) _run_jump_menu: positional ``log`` + positional-with-default
    # ``owned_ship=None`` dropped; verifies defaults alignment logic.
    jump_menu = _find_func(tree, "_run_jump_menu")
    jm_args = [a.arg for a in jump_menu.args.args]
    assert jm_args == ["ctx", "jp", "target_system_id"], (
        f"_run_jump_menu should drop log + owned_ship; got {jm_args}"
    )
    assert len(jump_menu.args.defaults) == 0, (
        f"_run_jump_menu should have NO positional defaults after drop; "
        f"got {[ast.dump(d) for d in jump_menu.args.defaults]}"
    )
    has_owned_ship_attr = any(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "ctx"
        and n.attr == "player_owned_ship"
        for n in ast.walk(jump_menu)
    )
    assert has_owned_ship_attr, (
        "_run_jump_menu body should contain ``ctx.player_owned_ship``"
    )

    # (11) Cross-modal call: ``_run_ship_menu`` -> ``_run_ship_view``.
    ship_menu = _find_func(tree, "_run_ship_menu")
    sm_args = [a.arg for a in ship_menu.args.args]
    assert sm_args == ["ctx"], (
        f"_run_ship_menu should have only ctx after migration; "
        f"got {sm_args}"
    )
    sm_calls = [
        c for c in _calls_in_body(tree, "_run_ship_menu")
        if isinstance(c.func, ast.Name) and c.func.id in TARGET_FUNCTIONS
    ]
    assert len(sm_calls) == 1, (
        f"_run_ship_menu should call exactly 1 other modal; "
        f"got {[ast.dump(c.func) for c in sm_calls]}"
    )
    assert sm_calls[0].func.id == "_run_ship_view", (
        f"_run_ship_menu should call _run_ship_view; "
        f"got {sm_calls[0].func.id}"
    )
    assert isinstance(sm_calls[0].args[0], ast.Name) and sm_calls[0].args[0].id == "ctx", (
        f"cross-modal call site should rename context -> ctx; "
        f"got {ast.dump(sm_calls[0].args[0])}"
    )


if __name__ == "__main__":
    smoke_test()
    print(f"{__name__}: structural smoke test passed.")
