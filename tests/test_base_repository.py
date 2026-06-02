from sqlalchemy.orm import Mapped, mapped_column

from data.db import Base, Database
from data.repositories.base_repository import BaseRepository


class _Widget(Base):
    __tablename__ = "_widget_test"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class _WidgetRepo(BaseRepository[_Widget]):
    model = _Widget


def test_crud_roundtrip(tmp_path):
    db = Database(tmp_path / "r.db")
    db.create_all()
    with db.session() as session:
        repo = _WidgetRepo(session)
        widget = repo.add(_Widget(name="alpha"))
        assert widget.id is not None
        assert repo.get(widget.id).name == "alpha"
        assert len(repo.all()) == 1
        repo.delete(widget)
        assert repo.all() == []
