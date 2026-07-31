#  Emergency Hospital Triage MCP Server

An Intelligent Model Context Protocol (MCP) server built to handle emergency hospital triage operations, manage patient flow, and optimize medical priorities using LLMs.

---

##  Features

* **Patient Triage Management:** Automatically assess and assign emergency severity index (ESI) levels.
* **Database Integration:** Persistent storage for tracking patient status and medical triage histories.
* **FastMCP Powered:** High-performance, lightweight execution using FastMCP.
* **Standardized Protocol:** Fully compatible with MCP-supported clients (like Claude Desktop and custom AI Agents).

---

##  Tech Stack

* **Language:** Python 3.10+
* **Framework:** FastMCP / Pydantic
* **Database:** SQLite (stored in `/db`)

---

## Repository Structure

```text
.
├── db/            # Database files and seed data
├── MCP.py         # Primary MCP server entry point and tools setup
└── README.md      # Project documentation
