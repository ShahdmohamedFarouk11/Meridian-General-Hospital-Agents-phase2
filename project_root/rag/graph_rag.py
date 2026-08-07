from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

class GraphRAG:
    """Graph RAG over legal entities and relationships (Bonus Component)."""
    def __init__(self):
        self.nodes = set()
        self.edges = defaultdict(list)

    def add_relationship(self, entity1: str, relation: str, entity2: str, metadata: Optional[Dict[str, Any]] = None):
        e1, e2 = entity1.strip(), entity2.strip()
        self.nodes.add(e1)
        self.nodes.add(e2)
        self.edges[e1].append({"relation": relation, "target": e2, "metadata": metadata or {}})
        self.edges[e2].append({"relation": f"reverse_{relation}", "target": e1, "metadata": metadata or {}})

    def query_entity_network(self, entity: str, depth: int = 2) -> Dict[str, Any]:
        visited = set()
        subgraph = []

        def traverse(curr: str, current_depth: int):
            if current_depth > depth or curr in visited:
                return
            visited.add(curr)
            for neighbor in self.edges[curr]:
                subgraph.append({
                    "source": curr,
                    "relation": neighbor["relation"],
                    "target": neighbor["target"]
                })
                traverse(neighbor["target"], current_depth + 1)

        traverse(entity, 0)
        return {
            "root_entity": entity,
            "connected_entities": list(visited),
            "relationships": subgraph
        }