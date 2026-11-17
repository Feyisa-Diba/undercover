import type { SectionRef } from "../api";
import { documentNames } from "../format";

export function SectionsRead({
  sections,
}: Readonly<{ sections: SectionRef[] }>) {
  return (
    <section className="panel" aria-labelledby="sections-title">
      <h2 id="sections-title">Sections read</h2>
      {sections.length === 0 ? (
        <p className="muted">
          The sections of the policy wording and the claims manual the agent
          reads for this claim appear here.
        </p>
      ) : (
        <ul className="sections-read">
          {sections.map((section) => (
            <li key={`${section.document}-${String(section.section)}`}>
              <span className="muted">{documentNames[section.document]}</span>{" "}
              {section.section}. {section.title}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
