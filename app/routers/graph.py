from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.graph_service import graph_to_dict

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/")
def get_graph(db: Session = Depends(get_db)):
    return graph_to_dict(db)
