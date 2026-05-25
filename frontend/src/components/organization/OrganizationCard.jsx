import "../../styles/OrganizationCard.css";

function OrganizationCard({ organization }) {
  const initials = organization.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <article className="org-card">
      <div className="org-card-header">
        <div className="org-avatar" aria-hidden="true">
          {initials}
        </div>
        <div className="org-card-meta">
          <h2 className="org-card-name">{organization.name}</h2>
          <span className="org-code-badge">{organization.code}</span>
        </div>
      </div>
      {organization.description && (
        <p className="org-card-description">{organization.description}</p>
      )}
      {organization.website && (
        <a
          href={organization.website}
          className="org-card-website"
          target="_blank"
          rel="noopener noreferrer"
        >
          Visit website
        </a>
      )}
    </article>
  );
}

export default OrganizationCard;
