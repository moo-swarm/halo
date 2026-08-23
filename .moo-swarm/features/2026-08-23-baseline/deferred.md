# Deferred Decisions — baseline

<!-- Append entries using: talaka/shared/deferred/tools/defer.sh --feature <path> ... -->

## DD-001: JS test infrastructure
- **Assigned to:** requirements-eliciting
- **Deferred by:** requirements-eliciting
- **Date:** 2026-08-23
- **Trigger:** second UI regression, or first feature touching dashboard.js logic beyond markup
- **Status:** open
- **Context:** AC2/AC4/AC6/AC7 are browser-runtime behaviours with no harness today; mirrors halo-hardening D3. Structural guards + manual smoke suffice until then.

## DD-002: Exporter generalization beyond _align-rail_ scan
- **Assigned to:** requirements-eliciting
- **Deferred by:** requirements-eliciting
- **Date:** 2026-08-23
- **Trigger:** project roster diverges from the hardcoded PROJECTS_DIR coverage
- **Status:** open
- **Context:** PROJECTS_DIR and gh org are hardcoded in scripts/moo-export-data.py:10,88; fine while all swarm projects live on one shared bus.

## DD-003: Custom domain halo.sh
- **Assigned to:** requirements-eliciting
- **Deferred by:** requirements-eliciting
- **Date:** 2026-08-23
- **Trigger:** DNS configured for apex domain
- **Status:** open
- **Context:** CNAME removed at 89a0dca pending DNS; AC-N17 tracks restoration.

## DD-004: Localisation beyond English
- **Assigned to:** requirements-eliciting
- **Deferred by:** requirements-eliciting
- **Date:** 2026-08-23
- **Trigger:** demonstrated non-English audience for the dashboard
- **Status:** open
- **Context:** UI strings are inline English in dashboard.js EMPTY_MESSAGES and index.html; no demand signal yet.
