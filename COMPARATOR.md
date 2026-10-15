# Accord — authoritative comparator and provenance

**Product:** Accord, the United Hampshire Government's Whitehall-derived publishing application.
**Original upstream:** [alphagov/whitehall](https://github.com/alphagov/whitehall).
**Original UK operational product:** Whitehall / Whitehall Admin, the application used by authorised GOV.UK publishers to maintain government organisations, people, roles, policies, news, publications and editions.
**Official architectural evidence:** [GOV.UK Whitehall developer documentation](https://docs.publishing.service.gov.uk/repos/whitehall.html), [GOV.UK publishing architecture](https://docs.publishing.service.gov.uk/manual/architecture-shallow-dive.html), [Whitehall edition workflow](https://docs.publishing.service.gov.uk/repos/whitehall/edition-workflow.html).
**Implementation class:** Exact UK-source adoption with the necessary United Hampshire identity, competent-organisation, domain, language, publication and territorial adaptations.

## Institutional and record boundaries
Accord is a government publishing **application**, not a ministry, statutory authority, HR service, legal casework system, general-purpose staff portal or source of ministerial appointment authority. The actual editorial content is owned by the institution competent to publish it. GOV.UH's digital publishing administration operates the application and its technical supporting services. Account privileges through publishing Signon are separately authorised.

Accord manages native editorial records, edition history and institutional publishing relationships. It sends structured material through the original Publishing API to Content Store, Router, search and the appropriate public renderers. It does not maintain immigration/citizenship status, personnel, police intelligence or payroll.

## Source integrity and UH adaptations
Preserve the source's original attribution, licensing, repository history, application model, audit and workflow semantics. The *external* application identity is Accord. Original internal code, tables and compatibility interfaces with the name Whitehall may remain where changing them would break the maintained upstream implementation.

Approved organisation marks must be controlled and provided by the owning institution; substitute UK Royal Arms are not permitted as UH assets. Interior Office has its own crest; Government Leaders' offices use the Parliament crest. Directory and organisation-page rendering must preserve the previously approved type-specific treatment. Publication authority and assets reside in the native editor and associated approved asset/components pipeline.

## Evidence required before acceptance
An authorised publisher and reviewer must prove create → edit → preview → review → publish → update → withdraw; correct role/organisation restrictions; record preservation; Publishing API/Content Store/Router/Search consistency; correct public body classification and crest placement; browser/accessibility checks; source SHA and image digest receipts; isolated recovery and rollback. A public HTTP 200, running container, or source checkout alone is not acceptance.

**Status of this file:** Comparator and implementation-boundary documentation. It is not a deployment certificate and does not appoint editors or approve publication.
