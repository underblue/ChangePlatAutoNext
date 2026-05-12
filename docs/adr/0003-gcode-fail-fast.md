# ADR 0003: Fail Fast on Unsafe G-code Insertion

## Status

Accepted.

## Context

Automatic plate change G-code moves hardware. Inserting it at an uncertain location could create mechanical risk.

## Decision

The default insertion strategy must fail if the expected finish-sound marker block is missing or ambiguous. Riskier append behavior may exist only as an explicit expert option with warning.

## Consequences

- Some unusual G-code files will require user action.
- The default behavior is safer and easier to reason about.
- Tests must cover missing marker behavior.
