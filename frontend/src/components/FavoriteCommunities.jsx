import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";

export default function FavoriteCommunities() {
  const [favorites, setFavorites] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get("/api/me/favorites/")
      .then((res) => {
        if (!cancelled) setFavorites(res.data.favorites ?? []);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load your favorite communities.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <p className="landing-favorites-empty">{error}</p>;
  if (!favorites || favorites.length === 0) return null;

  return (
    <section className="landing-favorites" aria-label="Favorite communities">
      <h2 className="landing-favorites-title">Favorites</h2>
      <ul className="landing-favorites-list">
        {favorites.map((org) => (
          <li key={org.id}>
            <Link to={`/org/${org.slug}/hub`} className="landing-favorites-link">
              <span className="landing-favorites-star" aria-hidden="true">
                ★
              </span>
              <span>
                <strong>{org.name}</strong>
                {(org.community_code || org.public_username) && (
                  <span className="landing-favorites-meta">
                    {org.community_code || `@${org.public_username}`}
                  </span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
