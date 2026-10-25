"""recherche plein texte PostgreSQL (remplace Elasticsearch)

Ajoute ``recipes.search_vector`` (tsvector, config ``french`` sur texte
désaccentué) pondéré : titre A, ingrédients B, description C, instructions D.

Le vecteur est maintenu par des triggers, quel que soit le chemin d'écriture
(API, imports, scripts) :
  • ``recipes``             : INSERT / UPDATE du titre, de la description ou des instructions ;
  • ``recipe_ingredients``  : ajout / modification / retrait d'un ingrédient ;
  • ``ingredients``         : renommage d'un ingrédient (toutes ses recettes).

``unaccent`` et ``pg_trgm`` (tolérance aux fautes sur le titre) sont des
extensions « trusted » (PG ≥ 13) : le rôle propriétaire de la base suffit.

Revision ID: e5f6a7b8c9d0
Revises: c2d3e4f5a6b7
Create Date: 2026-10-24 00:00:00.000000
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


_DOCUMENT_FUNCTION = """
CREATE OR REPLACE FUNCTION recipe_search_document(
    p_recipe_id integer, p_title text, p_description text, p_instructions text
) RETURNS tsvector
LANGUAGE sql STABLE AS $$
    SELECT
        setweight(to_tsvector('french', unaccent(coalesce(p_title, ''))), 'A')
        || setweight(to_tsvector('french', unaccent(coalesce((
            SELECT string_agg(i.name, ' ')
            FROM recipe_ingredients ri
            JOIN ingredients i ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = p_recipe_id
        ), ''))), 'B')
        || setweight(to_tsvector('french', unaccent(coalesce(p_description, ''))), 'C')
        || setweight(to_tsvector('french', unaccent(coalesce(p_instructions, ''))), 'D')
$$
"""

_REFRESH_SQL = """
UPDATE recipes
SET search_vector = recipe_search_document(id, title, description, instructions)
"""

_TRIGGERS = [
    """
CREATE OR REPLACE FUNCTION recipes_search_vector_trg() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.search_vector := recipe_search_document(
        NEW.id, NEW.title, NEW.description, NEW.instructions
    );
    RETURN NEW;
END
$$
""",
    """
CREATE TRIGGER recipes_search_vector
BEFORE INSERT OR UPDATE OF title, description, instructions ON recipes
FOR EACH ROW EXECUTE FUNCTION recipes_search_vector_trg()
""",
    """
CREATE OR REPLACE FUNCTION recipe_ingredients_search_vector_trg() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        UPDATE recipes
        SET search_vector = recipe_search_document(id, title, description, instructions)
        WHERE id = OLD.recipe_id;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        UPDATE recipes
        SET search_vector = recipe_search_document(id, title, description, instructions)
        WHERE id = NEW.recipe_id;
    END IF;
    RETURN NULL;
END
$$
""",
    """
CREATE TRIGGER recipe_ingredients_search_vector
AFTER INSERT OR UPDATE OR DELETE ON recipe_ingredients
FOR EACH ROW EXECUTE FUNCTION recipe_ingredients_search_vector_trg()
""",
    """
CREATE OR REPLACE FUNCTION ingredients_search_vector_trg() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE recipes
    SET search_vector = recipe_search_document(id, title, description, instructions)
    WHERE id IN (
        SELECT recipe_id FROM recipe_ingredients WHERE ingredient_id = NEW.id
    );
    RETURN NULL;
END
$$
""",
    """
CREATE TRIGGER ingredients_search_vector
AFTER UPDATE OF name ON ingredients
FOR EACH ROW EXECUTE FUNCTION ingredients_search_vector_trg()
""",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "recipes",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(_DOCUMENT_FUNCTION)
    for statement in _TRIGGERS:
        op.execute(statement)
    op.execute(_REFRESH_SQL)
    op.create_index(
        "ix_recipes_search_vector",
        "recipes",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_recipes_search_vector", table_name="recipes")
    op.execute("DROP TRIGGER IF EXISTS ingredients_search_vector ON ingredients")
    op.execute(
        "DROP TRIGGER IF EXISTS recipe_ingredients_search_vector ON recipe_ingredients"
    )
    op.execute("DROP TRIGGER IF EXISTS recipes_search_vector ON recipes")
    op.execute("DROP FUNCTION IF EXISTS ingredients_search_vector_trg()")
    op.execute("DROP FUNCTION IF EXISTS recipe_ingredients_search_vector_trg()")
    op.execute("DROP FUNCTION IF EXISTS recipes_search_vector_trg()")
    op.execute(
        "DROP FUNCTION IF EXISTS recipe_search_document(integer, text, text, text)"
    )
    op.drop_column("recipes", "search_vector")
    # Extensions conservées : partagées, sans coût, éventuellement utilisées ailleurs.
