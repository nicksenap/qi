import pytest

from qi.java_parser import JavaParser


@pytest.fixture
def java_parser():
    return JavaParser()


def test_parse_simple_method(java_parser, tmp_path):
    """Test parsing a simple Java method."""
    test_file = tmp_path / "Test.java"
    test_file.write_text("""
package com.test;

public class Test {
    public void simpleMethod() {
        System.out.println("Hello");
    }
}
""")

    tree = java_parser.parse_file(test_file)
    methods = java_parser.extract_methods(tree, test_file.read_bytes())

    assert len(methods) == 1
    method = methods[0]
    assert method.name == "simpleMethod"
    assert method.modifiers == ["public"]
    assert method.return_type == "void"
    assert method.parameters == []
    assert "System.out.println" in method.body


def test_parse_method_with_annotations(java_parser, tmp_path):
    """Test parsing a method with annotations."""
    test_file = tmp_path / "Test.java"
    test_file.write_text("""
package com.test;

public class Test {
    @Override
    public String toString() {
        return "Test";
    }
}
""")

    tree = java_parser.parse_file(test_file)
    methods = java_parser.extract_methods(tree, test_file.read_bytes())

    assert len(methods) == 1
    method = methods[0]
    assert method.name == "toString"
    assert method.modifiers == ["public"]
    assert method.return_type == "String"
    assert method.parameters == []
    assert method.annotations == ["@Override"]


def test_merge_java_files(java_parser, tmp_path):
    """Test merging two Java files."""
    source_file = tmp_path / "Generated.java"
    source_file.write_text("""
package com.test;

public class Test {
    public void method() {
        System.out.println("Generated");
    }
}
""")

    target_file = tmp_path / "Existing.java"
    target_file.write_text("""
package com.test;

public class Test {
    public void method() {
        System.out.println("Custom");
        System.out.println("Implementation");
    }
}
""")

    merged = java_parser.merge_java_files(source_file, target_file)

    # The merged content should preserve the custom implementation
    assert "Custom" in merged
    assert "Implementation" in merged
    assert "Generated" not in merged


def test_merge_with_multiple_methods(java_parser, tmp_path):
    """Test merging files with multiple methods."""
    source_file = tmp_path / "Generated.java"
    source_content = (
        "package com.test;\n"
        "\n"
        "public class Test {\n"
        "    public void method1() {\n"
        '        System.out.println("Generated1");\n'
        "    }\n"
        "\n"
        "    public void method2() {\n"
        '        System.out.println("Generated2");\n'
        "    }\n"
        "}\n"
    )
    source_file.write_text(source_content)

    target_file = tmp_path / "Existing.java"
    target_content = (
        "package com.test;\n"
        "\n"
        "public class Test {\n"
        "    public void method1() {\n"
        '        System.out.println("Custom1");\n'
        "    }\n"
        "\n"
        "    public void method2() {\n"
        '        System.out.println("Custom2");\n'
        "    }\n"
        "}\n"
    )
    target_file.write_text(target_content)

    merged = java_parser.merge_java_files(source_file, target_file)

    # Both custom implementations should be preserved
    assert "Custom1" in merged
    assert "Custom2" in merged
    assert "Generated1" not in merged
    assert "Generated2" not in merged


def test_merge_with_complex_signatures(java_parser, tmp_path):
    """Test merging methods with complex signatures."""
    source_file = tmp_path / "Generated.java"
    source_file.write_text("""
package com.test;

public class Test {
    @Override
    public List<String> complexMethod(Map<String, Object> param1, int[] param2) throws Exception {
        return Collections.emptyList();
    }
}
""")

    target_file = tmp_path / "Existing.java"
    target_file.write_text("""
package com.test;

public class Test {
    @Override
    public List<String> complexMethod(Map<String, Object> param1, int[] param2) throws Exception {
        // Custom implementation
        List<String> result = new ArrayList<>();
        result.add("Custom");
        return result;
    }
}
""")

    merged = java_parser.merge_java_files(source_file, target_file)

    # Custom implementation should be preserved
    assert "Custom" in merged
    assert "Collections.emptyList()" not in merged
