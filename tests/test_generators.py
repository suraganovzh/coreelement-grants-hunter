"""Tests for content generators."""

import pytest
from pathlib import Path
from src.generators.template_manager import TemplateManager


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class TestTemplateManager:
    def setup_method(self):
        self.manager = TemplateManager(TEMPLATE_DIR)

    def test_list_templates(self):
        templates = self.manager.list_templates()
        assert len(templates) >= 4
        assert "executive_summary" in templates
        assert "technical_approach" in templates

    def test_get_template(self):
        content = self.manager.get_template("executive_summary")
        assert "Executive Summary" in content
        assert "Core Element" in content

    def test_get_nonexistent_template(self):
        content = self.manager.get_template("nonexistent_template")
        assert content == ""

    def test_render_template(self):
        content = self.manager.get_template("executive_summary")
        # Templates use [CUSTOMIZE: ...] markers, not $variable substitution
        assert "[CUSTOMIZE:" in content

    def test_all_templates_have_customize_markers(self):
        for name in self.manager.list_templates():
            content = self.manager.get_template(name)
            assert "[CUSTOMIZE:" in content, f"Template {name} missing [CUSTOMIZE:] markers"
