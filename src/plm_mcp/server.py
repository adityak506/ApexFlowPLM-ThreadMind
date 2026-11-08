"""FastMCP Server initialization and tool registration for Mock PLM."""

from mcp.server.fastmcp import FastMCP
from plm_mcp import tools

# Initialize FastMCP Server
mcp = FastMCP(
    name="plm-mcp",
    instructions=(
        "Model Context Protocol server exposing a PTC Windchill-inspired Product Lifecycle Management (PLM) system. "
        "Supports parts, revision.iteration versioning (e.g. A.1 -> B.1), lifecycle states, multi-level BOM usage links, "
        "documents, change management (ECR & ECN), and supplier sourcing (AML/AVL). "
        "All mutation tools default to safe draft/dry-run mode and require confirm=True to persist state changes."
    ),
)

# -----------------------------------------------------------------------------
# Part Management Tools
# -----------------------------------------------------------------------------
mcp.tool()(tools.get_part)
mcp.tool()(tools.search_parts)
mcp.tool()(tools.create_part)
mcp.tool()(tools.revise_part)
mcp.tool()(tools.iterate_part)
mcp.tool()(tools.set_part_lifecycle_state)

# -----------------------------------------------------------------------------
# Bill of Materials (BOM) & Product Structure Tools
# -----------------------------------------------------------------------------
mcp.tool()(tools.get_part_bom)
mcp.tool()(tools.get_where_used)
mcp.tool()(tools.add_bom_component)
mcp.tool()(tools.remove_bom_component)

# -----------------------------------------------------------------------------
# Document Management Tools
# -----------------------------------------------------------------------------
mcp.tool()(tools.get_document)
mcp.tool()(tools.search_documents)
mcp.tool()(tools.create_document)
mcp.tool()(tools.link_document_to_part)

# -----------------------------------------------------------------------------
# Change Management Tools (ECR & ECN)
# -----------------------------------------------------------------------------
mcp.tool()(tools.create_change_request)
mcp.tool()(tools.get_change_request)
mcp.tool()(tools.create_change_notice)
mcp.tool()(tools.get_change_notice)
mcp.tool()(tools.add_change_affected_item)
mcp.tool()(tools.execute_change_notice)

# -----------------------------------------------------------------------------
# Supplier & Sourcing Management Tools (AML/AVL)
# -----------------------------------------------------------------------------
mcp.tool()(tools.search_manufacturers)
mcp.tool()(tools.get_part_aml)
mcp.tool()(tools.add_manufacturer)
mcp.tool()(tools.add_manufacturer_part)
mcp.tool()(tools.set_sourcing_link)


def run() -> None:
    """Run the FastMCP server with stdio transport."""
    mcp.run()


if __name__ == "__main__":
    run()

