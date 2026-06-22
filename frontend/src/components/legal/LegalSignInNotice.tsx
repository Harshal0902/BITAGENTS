import Link from "next/link";
import { LEGAL_LINKS, LEGAL_SIGN_IN_NOTICE } from "@/lib/legal";

export function LegalSignInNotice() {
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      {LEGAL_SIGN_IN_NOTICE}{" "}
      <Link href={LEGAL_LINKS.terms} className="text-signal underline-offset-2 hover:underline">
        Terms
      </Link>
      ,{" "}
      <Link href={LEGAL_LINKS.privacy} className="text-signal underline-offset-2 hover:underline">
        Privacy
      </Link>
      ,{" "}
      <Link
        href={LEGAL_LINKS.riskDisclaimer}
        className="text-signal underline-offset-2 hover:underline"
      >
        Risk Disclaimer
      </Link>
      .
    </p>
  );
}
