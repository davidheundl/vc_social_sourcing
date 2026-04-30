from typing import Any
import networkx as nx
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.relationship import Relationship


def build_graph(db: Session) -> nx.DiGraph:
    G = nx.DiGraph()

    profiles = db.query(Profile).all()
    for p in profiles:
        G.add_node(
            p.id,
            name=p.full_name,
            role=p.role or "",
            country=p.country or "",
            is_seed=p.is_seed,
            company=p.company_name_raw or "",
        )

    rels = db.query(Relationship).all()
    for r in rels:
        G.add_edge(r.source_id, r.target_id, rel_type=r.rel_type, weight=r.weight)

    return G


def graph_to_dict(db: Session) -> dict[str, Any]:
    G = build_graph(db)

    centrality = nx.degree_centrality(G)

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        nodes.append({
            "id": node_id,
            "centrality": round(centrality.get(node_id, 0.0), 4),
            **attrs,
        })

    edges = [
        {"source": u, "target": v, "rel_type": d.get("rel_type"), "weight": d.get("weight", 1)}
        for u, v, d in G.edges(data=True)
    ]

    return {"nodes": nodes, "edges": edges}


def vc_proximity_score(profile_id: int, db: Session) -> int:
    G = build_graph(db)
    seed_ids = [
        p.id for p in db.query(Profile).filter(Profile.is_seed == True).all()
    ]
    if not seed_ids or profile_id not in G:
        return 0

    min_dist = float("inf")
    for seed_id in seed_ids:
        try:
            dist = nx.shortest_path_length(G, source=profile_id, target=seed_id)
            min_dist = min(min_dist, dist)
        except nx.NetworkXNoPath:
            continue

    if min_dist == 1:
        return 20
    if min_dist == 2:
        return 10
    if min_dist == 3:
        return 5
    return 0
