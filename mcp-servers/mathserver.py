from fastmcp import FastMCP

mcp = FastMCP("mathMCPServerSTDIO")


@mcp.tool(name="add_tool")
def add(a: int, b: int) -> str:
    """Add two integers.

    Args:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The sum of `a` and `b`.
    """
    return f"Sum  {a+b}"


@mcp.tool()
def multiply(a: int, b: int) -> str:
    """Multiply two integers.

    Args:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The product of `a` and `b`.
    """
    return f"Product:  {a*b}"


if __name__ == "__main__":
    mcp.run()
