"""Admin-approved cross-supplier product equivalences.

Used by ``ProductRepository.find_alternate_in_stock`` as the deterministic,
admin-curated layer of failover: when the primary supplier is out of stock,
an approved pair here routes the order to the exact equivalent offer instead
of relying on fuzzy name matching alone.
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer, UniqueConstraint
from sqladmin import ModelView

from models.base import Base


class ApprovedEquivalent(Base):
    """A bidirectional, admin-approved pair of equivalent ``product_id`` values.

    Storing ``(A, B)`` also makes ``B`` an alternate source for ``A``; the pair
    is symmetric by convention and enforced in the lookup.
    """

    __tablename__ = "approved_equivalents"
    __table_args__ = (
        UniqueConstraint("product_id", "equivalent_product_id", name="uq_approved_equiv_pair"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    equivalent_product_id = Column(BigInteger, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"ApprovedEquivalent[{self.product_id} <-> {self.equivalent_product_id}]"


class ApprovedEquivalentAdmin(ModelView, model=ApprovedEquivalent):
    name = "Approved Equivalence"
    name_plural = "Approved Equivalences"
    icon = "fa-solid fa-link"
    category = "Catalog"

    column_list = [
        ApprovedEquivalent.id,
        ApprovedEquivalent.product_id,
        ApprovedEquivalent.equivalent_product_id,
        ApprovedEquivalent.created_at,
    ]
    column_labels = {
        ApprovedEquivalent.product_id: "Product ID A",
        ApprovedEquivalent.equivalent_product_id: "Equivalent Product ID B",
        ApprovedEquivalent.created_at: "Created",
    }
    column_default_sort = [(ApprovedEquivalent.created_at, True)]
    column_searchable_list = [
        ApprovedEquivalent.product_id,
        ApprovedEquivalent.equivalent_product_id,
    ]
    form_columns = [
        ApprovedEquivalent.product_id,
        ApprovedEquivalent.equivalent_product_id,
    ]

    can_delete = True
    can_create = True
    can_edit = True
    can_export = True