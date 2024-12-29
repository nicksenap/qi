from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Language, Node, Parser, Tree
from tree_sitter_java import language


@dataclass
class JavaMethod:
    """Represents a Java method with its components."""

    name: str
    modifiers: list[str]
    return_type: str
    parameters: list[str]
    body: str
    annotations: list[str]
    start_byte: int
    end_byte: int
    source_text: str

    @property
    def signature(self) -> str:
        """Get the method signature without annotations."""
        return f"{' '.join(self.modifiers)} {self.return_type} {self.name}({', '.join(self.parameters)})"


class JavaParser:
    """Parser for Java source code using tree-sitter."""

    def __init__(self):
        self.parser = Parser()
        self.parser.language = Language(language())

    @staticmethod
    def _get_node_text(node: Node, source: bytes) -> str:
        """Get text from a node."""
        return source[node.start_byte : node.end_byte].decode("utf-8")

    def _extract_method_info(self, method_node: Node, source: bytes) -> JavaMethod:
        """Extract method information from a method declaration node."""
        modifiers = []
        annotations = []
        return_type = ""
        method_name = ""
        parameters = []

        for child in method_node.children:
            if child.type == "modifiers":
                for modifier in child.children:
                    if modifier.type == "marker_annotation":
                        annotations.append(self._get_node_text(modifier, source))
                    else:
                        modifiers.append(self._get_node_text(modifier, source))
            elif child.type in {"type_identifier", "void_type"}:
                return_type = self._get_node_text(child, source)
            elif child.type == "identifier":
                method_name = self._get_node_text(child, source)
            elif child.type == "formal_parameters":
                for param in child.children:
                    if param.type == "formal_parameter":
                        parameters.append(self._get_node_text(param, source))

        # Get method body
        body_node = next((child for child in method_node.children if child.type == "block"), None)
        body = self._get_node_text(body_node, source) if body_node else ""

        return JavaMethod(
            name=method_name,
            modifiers=modifiers,
            return_type=return_type,
            parameters=parameters,
            body=body,
            annotations=annotations,
            start_byte=method_node.start_byte,
            end_byte=method_node.end_byte,
            source_text=self._get_node_text(method_node, source),
        )

    def parse_file(self, file_path: str | Path) -> Tree:
        """Parse a Java file and return its AST."""
        with open(file_path, "rb") as f:
            source = f.read()
        return self.parser.parse(source)

    def extract_methods(self, tree: Tree, source: bytes) -> list[JavaMethod]:
        """Extract all methods from a parsed Java file."""
        methods = []

        def visit_node(node: Node):
            if node.type == "method_declaration":
                methods.append(self._extract_method_info(node, source))
            for child in node.children:
                visit_node(child)

        visit_node(tree.root_node)
        return methods

    def merge_java_files(self, source_file: str | Path, target_file: str | Path) -> str:
        """Merge two Java files, preserving custom modifications in the target file."""
        if not Path(target_file).exists():
            with open(source_file) as f:
                return f.read()

        # Parse both files
        with open(source_file, "rb") as f:
            source_bytes = f.read()
            source_tree = self.parser.parse(source_bytes)
            source_methods = {m.signature: m for m in self.extract_methods(source_tree, source_bytes)}

        with open(target_file, "rb") as f:
            target_bytes = f.read()
            target_tree = self.parser.parse(target_bytes)
            target_methods = {m.signature: m for m in self.extract_methods(target_tree, target_bytes)}

        # Start with the source file content
        result = source_bytes.decode("utf-8")

        # Replace each method body with the corresponding target method body if it exists
        offset = 0
        for signature, source_method in sorted(source_methods.items(), key=lambda x: x[1].start_byte):
            if signature in target_methods:
                target_method = target_methods[signature]
                # Calculate the actual position in the modified content
                start_pos = source_method.start_byte + offset
                end_pos = source_method.end_byte + offset

                # Replace the entire method
                result = result[:start_pos] + target_method.source_text + result[end_pos:]

                # Update offset for subsequent replacements
                offset += len(target_method.source_text) - (source_method.end_byte - source_method.start_byte)

        return result
