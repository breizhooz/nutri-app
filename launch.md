Page Login — Split-screen avec panneau décoratif animé (orbes émeraude, grille géométrique), typographie
  Cormorant Garamond, stats en bas à gauche.

  Dashboard — Tout s'affiche correctement :
  - Navbar sticky avec logo + bouton déconnexion
  - Profil : montre les états vides car le faux token est rejeté par l'API (comportement normal)
  - Santé des services : tous en KO car les services Docker ne tournent pas — exactement le comportement attendu
  - Recettes / Menu : états vides affichés proprement
  
  Quand vous lancerez avec docker compose up et un vrai compte, tout se remplira.

  ---
  Pour utiliser l'app :
  cd frontend
  npm run dev   # http://localhost:5173
  
  Je vais enlever playwright des dépendances de prod (il a été ajouté automatiquement) :


####
Script de nettoyage
docker compose exec service-recipe python -m scripts.drop_recipe          # avec confirmation
docker compose exec service-recipe python -m scripts.drop_recipe --yes     # sans prompt
