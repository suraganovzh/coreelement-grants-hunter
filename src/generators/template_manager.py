"""Template manager — loads and manages reusable document templates."""

from pathlib import Path
from string import Template

from src.utils.logger import setup_logger

logger = setup_logger("template_manager")

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class TemplateManager:
    """Manage reusable templates for grant applications."""

    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR

    def get_template(self, name: str) -> str:
        """Load a template by name.

        Args:
            name: Template filename without extension (e.g., 'executive_summary').

        Returns:
            Template content string, or empty string if not found.
        """
        path = self.template_dir / f"{name}.md"
        if not path.exists():
            logger.warning("Template not found: %s", path)
            return ""
        return path.read_text()

    def list_templates(self) -> list[str]:
        """List all available template names."""
        if not self.template_dir.exists():
            return []
        return [p.stem for p in sorted(self.template_dir.glob("*.md"))]

    def render_template(self, name: str, variables: dict) -> str:
        """Render a template with variable substitution.

        Uses Python's string.Template for safe substitution.
        Variables in templates use $variable_name or ${variable_name} syntax.

        Args:
            name: Template name.
            variables: Dict of variable names to values.

        Returns:
            Rendered template string.
        """
        content = self.get_template(name)
        if not content:
            return ""

        try:
            tmpl = Template(content)
            return tmpl.safe_substitute(variables)
        except Exception as e:
            logger.error("Failed to render template %s: %s", name, e)
            return content
