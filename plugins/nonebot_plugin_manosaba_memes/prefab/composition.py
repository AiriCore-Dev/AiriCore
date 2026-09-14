from collections.abc import Iterable

from .models import CharacterData, CompositionData


class Composition:


    def __init__(
        self, character_data: CharacterData, composition_data: CompositionData | None
    ):


        self._character_data = character_data
        self._composition_data = composition_data

        self._root_id = 0
        self._children: dict[int, list[int]] = self._build_children()
        self._parent: dict[int, int] = self._build_parent()
        self._sprite_nodes: set[int] = {
            idx for idx, node in enumerate(character_data.nodes) if node.sprite
        }
        self._initially_enabled: set[int] = {
            idx
            for idx, node in enumerate(character_data.nodes)
            if node.sprite and node.sprite.enabled
        }


    def resolve(self, *keys: str, use_defaults: bool = True) -> set[int]:


        if not self._composition_data:
            raise RuntimeError("Composition map is not available for this prefab.")

        active: set[int] = set(self._initially_enabled)


        if use_defaults and self._composition_data.default_appearance:
            self._apply_composition_string(
                self._composition_data.default_appearance, active, recursion_stack=[]
            )


        for raw_key in keys:
            self._apply_composition_string(raw_key, active, recursion_stack=[])

        return active

    def apply(self, active: set[int], *keys: str) -> set[int]:


        if not self._composition_data:
            raise RuntimeError("Composition map is not available for this prefab.")

        result = set(active)
        for raw_key in keys:
            self._apply_composition_string(raw_key, result, recursion_stack=[])
        return result

    def affected_nodes(self, *keys: str) -> set[int]:


        enabled_from_empty = self.apply(set(), *keys)
        enabled_from_full = self.apply(set(self._sprite_nodes), *keys)
        return enabled_from_empty | (self._sprite_nodes - enabled_from_full)

    @property
    def sprite_nodes(self) -> set[int]:
        return set(self._sprite_nodes)

    @property
    def initially_enabled(self) -> set[int]:
        return set(self._initially_enabled)

    def get_available_keys(self) -> list[str]:


        if not self._composition_data:
            return []
        return sorted(self._composition_data.entries.keys())

    def get_entries(self) -> dict[str, str]:

        if not self._composition_data:
            return {}
        return dict(self._composition_data.entries)

    def get_default_appearance(self) -> str:


        if not self._composition_data:
            return ""
        return self._composition_data.default_appearance


    def _build_children(self) -> dict[int, list[int]]:
        children: dict[int, list[int]] = {}
        for idx, node in enumerate(self._character_data.nodes):
            if node.children:
                children[idx] = list(node.children)
        return children

    def _build_parent(self) -> dict[int, int]:
        parent: dict[int, int] = {}
        for idx, node in enumerate(self._character_data.nodes):
            if not node.children:
                continue
            for child in node.children:
                parent[child] = idx
        return parent

    def _apply_composition_string(
        self, composition: str, active: set[int], recursion_stack: list[str]
    ) -> None:

        tokens = [token.strip() for token in composition.split(",") if token.strip()]
        for token in tokens:
            self._apply_token(token, active, recursion_stack)

    def _apply_token(
        self, token: str, active: set[int], recursion_stack: list[str]
    ) -> None:

        if self._composition_data and token in self._composition_data.entries:
            if token in recursion_stack:
                raise ValueError(
                    f"Recursive composition reference detected: {' -> '.join(recursion_stack + [token])}"
                )
            recursion_stack.append(token)
            nested = self._composition_data.entries[token]
            self._apply_composition_string(nested, active, recursion_stack)
            recursion_stack.pop()
            return


        self._apply_expression(token, active)

    def _apply_expression(self, expression: str, active: set[int]) -> None:

        op_index, op_char = self._find_operator(expression)
        if op_index is None:


            path = [part for part in expression.split("/") if part]
            target_id = (
                self._find_node_by_path(path)
                if len(path) > 1
                else self._find_descendant_by_name(self._root_id, expression)
            )
            if target_id is None:
                raise ValueError(f"Unable to locate layer '{expression}'.")
            self._enable_subtree(target_id, active)
            return

        group_part = expression[:op_index].strip()
        target_part = expression[op_index + 1 :].strip()

        group_path = [p for p in group_part.split("/") if p] if group_part else []
        group_id = self._find_node_by_path(group_path)
        if group_id is None:
            raise ValueError(f"Unable to locate group path '{group_part or '<root>'}'.")

        if op_char == "+":
            target_id = self._resolve_target(group_id, target_part)
            self._enable_subtree(target_id, active)
        elif op_char == "-":
            target_id = self._resolve_target(group_id, target_part)
            self._disable_subtree(target_id, active)
        elif op_char == ">":
            if target_part:
                target_id = self._resolve_target(group_id, target_part)

                self._disable_subtree(group_id, active)
                self._enable_subtree(target_id, active)
            else:

                parent_id = self._parent.get(group_id)
                if parent_id is not None:
                    for sibling_id in self._children.get(parent_id, []):
                        if sibling_id != group_id:
                            self._disable_subtree(sibling_id, active)
                self._enable_subtree(group_id, active)
        else:
            raise ValueError(f"Unsupported composition operator '{op_char}'.")

    def _resolve_target(self, group_id: int, target_name: str) -> int:

        if not target_name:
            return group_id


        direct_child = self._find_child_by_name(group_id, target_name)
        if direct_child is not None:
            return direct_child

        descendant = self._find_descendant_by_name(group_id, target_name)
        if descendant is not None:
            return descendant

        raise ValueError(
            f"Unable to resolve target '{target_name}' under group '{self._character_data.nodes[group_id].name}'."
        )


    def _find_operator(self, expression: str) -> tuple[int | None, str | None]:
        for ch in (">", "+", "-"):
            idx = expression.find(ch)
            if idx != -1:
                return idx, ch
        return None, None

    def _find_node_by_path(self, path: Iterable[str]) -> int | None:
        current = self._root_id
        for name in path:
            current = self._find_child_by_name(current, name)
            if current is None:
                return None
        return current

    def _find_child_by_name(self, parent_id: int, name: str) -> int | None:
        for child_id in self._children.get(parent_id, []):
            if self._character_data.nodes[child_id].name == name:
                return child_id
        return None

    def _find_descendant_by_name(self, start_id: int, name: str) -> int | None:
        stack = [start_id]
        while stack:
            current = stack.pop()
            if self._character_data.nodes[current].name == name:
                return current
            stack.extend(self._children.get(current, []))
        return None


    def _collect_sprite_descendants(self, node_id: int) -> set[int]:
        collected: set[int] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in self._sprite_nodes:
                collected.add(current)
            stack.extend(self._children.get(current, []))
        return collected

    def _enable_subtree(self, node_id: int, active: set[int]) -> None:
        newly_enabled = self._collect_sprite_descendants(node_id)
        active.update(newly_enabled)


        for sprite_id in newly_enabled:
            self._enable_leaf_ancestor_siblings(sprite_id, active)

    def _disable_subtree(self, node_id: int, active: set[int]) -> None:
        active.difference_update(self._collect_sprite_descendants(node_id))

    def _enable_leaf_ancestor_siblings(self, node_id: int, active: set[int]) -> None:

        current = self._parent.get(node_id)
        while current is not None:
            parent_of_current = self._parent.get(current)
            if parent_of_current is None:
                break

            for sibling_id in self._children.get(parent_of_current, []):
                if sibling_id == current:
                    continue
                if self._is_leaf_sprite(sibling_id):
                    active.add(sibling_id)

            current = parent_of_current

    def _is_leaf_sprite(self, node_id: int) -> bool:
        return node_id in self._sprite_nodes and node_id not in self._children
