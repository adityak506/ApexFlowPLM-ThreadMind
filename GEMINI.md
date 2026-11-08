# Project: Mock PLM (Windchill-Style) MCP Server

## Overview
Mock Product Lifecycle Management (PLM) system inspired by PTC Windchill, exposed through a Model Context Protocol (MCP) server.

## Core Rules & Constraints

### 1. Technology Stack & Frameworks
- **Python Version**: Python 3.11+.
- **MCP Framework**: Use the official MCP Python SDK (`FastMCP`).

### 2. Architecture & Backend Abstraction
- **Strict Backend Interface**: All MCP tools must call the `PLMBackend` interface only. Never interact with SQLite or Windchill directly from tool implementations.
- **Backend Implementations**:
  - `MockBackend` (SQLite): Primary backend for local mock data and testing.
  - `WindchillBackend` (REST/OData): Planned integration for PTC Windchill instances.
- **Backend Selection**: Dynamic backend selection driven by the `PLM_BACKEND` environment variable (e.g., `PLM_BACKEND=mock` or `PLM_BACKEND=windchill`).
- **Normalized Schema**: All backends must return a normalized internal schema, ensuring tool callers and consumers receive consistent data structures regardless of the active backend.

### 3. Tool Design & Safety
- **Write Operation Safety**: All write/mutation tools must default to draft/dry-run mode.
- **Explicit Confirmation**: Applying state changes or executing mutations requires explicit `confirm=True`.

### 4. Code Quality, Typing & Testing
- **Tool Standards**: Every tool must include:
  - Comprehensive docstring explaining behavior, parameters, and return types.
  - Strict type hints on all arguments and return values.
  - Corresponding `pytest` unit/integration test coverage.

### 5. Security & Credentials
- **No Hardcoded Credentials**: Never hardcode credentials, tokens, passwords, or connection strings. Always source configuration from environment variables.

### 6. Windchill Integration Integrity
- **No Invented Endpoints**: Do not hallucinate or assume Windchill REST or OData endpoints.
- **Verification Marking**: Mark any uncertain endpoint, schema, or behavior with a `TODO` comment: `"verify against Windchill docs"`.

