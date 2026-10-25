"use client";

import { useLanguage } from "@/lib/language-context";
import {
  CLAIM_KIND_COPY,
  reviewNoteText,
  type CitedClaim,
  type ReviewNote,
} from "@/lib/recorded-demo";
import { Badge } from "./EvidencePanel";
import { GlossedText } from "./GlossedText";

/**
 * Under one recorded action: the claims it cites (collapsed, text as recorded), then the known
 * limitations a reviewer wrote about it. Shared by /demo and the Sample Workspace.
 */
export function ActionDetails({ claims, notes }: { claims: CitedClaim[]; notes: ReviewNote[] }) {
  const { copy, language } = useLanguage();
  if (claims.length === 0 && notes.length === 0) {
    return null;
  }
  return (
    <div className="action-details">
      {claims.length > 0 ? (
        <details className="action-details__claims">
          <summary>
            {copy("citedClaims")}:{" "}
            <span className="action-details__ids">{claims.map((claim) => claim.id).join(" · ")}</span>
          </summary>
          <ul>
            {claims.map((claim) => (
              <li key={claim.id}>
                <span className="action-details__id">{claim.id}</span>
                {claim.kind ? <Badge tone="muted">{copy(CLAIM_KIND_COPY[claim.kind])}</Badge> : null}
                <span>
                  {claim.text ? <GlossedText text={claim.text} /> : copy("citedClaimMissing")}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {notes.map((note, i) => (
        <p key={i} className="demo-finding__known" role="note">
          <strong>{copy("proposalKnownLimitation")}:</strong> {reviewNoteText(note, language)}
        </p>
      ))}
    </div>
  );
}
