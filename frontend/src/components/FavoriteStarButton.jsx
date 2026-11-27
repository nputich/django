function StarIcon({ filled }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="favorite-star-icon">
      <path
        d="M12 3.2l2.4 5.1 5.6.7-4.1 3.8 1.1 5.5L12 15.8 7 18.3l1.1-5.5L4 9l5.6-.7L12 3.2z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function FavoriteStarButton({ favorited, onClick, disabled, label }) {
  return (
    <button
      type="button"
      className={`favorite-star${favorited ? " favorite-star--on" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={favorited}
      aria-label={label || (favorited ? "Remove from favorites" : "Add to favorites")}
    >
      <StarIcon filled={favorited} />
    </button>
  );
}
