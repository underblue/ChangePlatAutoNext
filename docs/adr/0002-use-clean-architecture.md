# ADR 0002: Use Clean Architecture Boundaries

## Status

Accepted.

## Context

The existing implementation keeps most core logic outside Qt, which is good, but export orchestration still mixes ZIP staging, XML rewriting, G-code transforms, preview image composition, and business validation in one module.

## Decision

The redesign will separate domain, application, ports, adapters, and interfaces.

## Consequences

- G-code and 3MF behavior can be tested without GUI.
- CLI and GUI can share the same workflow.
- The system is easier for VibeCoding because tasks can own disjoint directories.
- More upfront structure is required.
