> **Independent conceptual review — source review only**  
> **Author:** Daria Lepikhina, Independent Researcher  
> **Original review:** 18 October 2026 · Published with the author's approval on 19 October 2026  
> **Scope:** XB-1 case X5 in the public Sovereign Veritas repository. This is not experimental reproduction, a whole-system audit, or evidence of actual harm.  
> **Editorial preparation:** Markdown layout and companion metadata prepared with ChatGPT (OpenAI GPT-6) at Chad Holland's direction; the authored review below is preserved.  

---

# Human oversight after an unrecorded action

*Comments on XB-1, case X5 | Sovereign Veritas*  
**Daria Lepikhina | 18 October 2026**

## Scope

Thank you, Chad, for sharing XB-1 and suggesting X5. I read the results, preregistration and probe code. This is a conceptual review of those materials, not an independent reproduction or an audit of the wider project.

X5 gives a useful example of why execution and recording need separate attention. The counting executor registers one simulated effect, but the evidence sink fails to write its record. This shows a gap in that execution and recording sequence. It does not model harm to a person or test how a human would respond.

## 1. What could a human reviewer actually know?

The experimenter knows that execution occurred because the counter is visible. My first question is whether someone investigating a comparable incident would have equally useful evidence. Visibility within a test should not be assumed to mean visibility for the person responsible for handling a failure.

A reviewer would need the requested action, its authorisation, the timing of execution and the recording error, and any confirmation available outside the affected ledger. Depending on the application, that might be a receiving system's acknowledgement or a verifiable change in state. Those are possible sources to investigate, not capabilities established by X5.

The error should also reach someone who can investigate, with a clear warning that execution may already have occurred. If the available evidence cannot settle that question, the result should remain uncertain. An absent record should not be treated as proof that nothing happened.

## 2. Who could act on that information?

Being able to investigate is different from being authorised and equipped to respond. Someone may be able to reconstruct events but lack permission to pause further attempts, obtain evidence from another system or arrange a remedy.

I would therefore identify a reachable owner for each remaining task, with the information, tools and time needed to carry it out. A coordinator can follow the case without holding every specialist power, but escalation needs to reach someone who can address a missing permission or resource. The reviewed materials do not establish how those human roles would work.

## 3. What would count as putting things right?

If the missing record is later created, that improves the account of what happened. It does not itself undo the executed action. In a future scenario involving a person, I would assess the record correction and the response to each consequence separately.

Useful distinctions would include: execution confirmed, record corrected, further effects contained, remedy proposed, remedy delivered, and loss still unresolved. Each needs evidence. The affected person should be able to explain consequences that the technical record does not capture and question whether a proposed remedy fits their circumstances.

X5 does not test these outcomes. I would present them as questions for extending the evaluation, rather than conclusions about a demonstrated failure to help someone.

## 4. What would be worth testing next?

A follow-up scenario could test whether a human receives an understandable alert, can check execution independently, and can initiate a suitable response within a useful period. It could also examine a repeat attempt after a recording failure. That particular retry sequence is not tested in X5; repeating an action with an uncertain outcome is a risk to investigate, not an observed result of this case.

For an affected person, I would look for an explanation of what is known and uncertain, a way to submit evidence or challenge the findings, and a clear contact and update point. If a loss cannot be undone, the response may eventually be concluded, but that remaining loss should still be acknowledged. A completed investigation is not evidence of restoration.

## My main observation

X5 identifies a concrete technical gap. The next question is whether a human can discover that gap, establish what happened and organise an effective response. I think keeping those questions separate would make a follow-up evaluation useful without asking the existing probe to demonstrate more than it was designed to show.

## Materials reviewed

- [`docs/EXECUTION_BOUNDARY_RESULTS.md`](https://github.com/holland202/sovereign-veritas/blob/main/docs/EXECUTION_BOUNDARY_RESULTS.md)
- [`docs/EXECUTION_BOUNDARY_PREREG.md`](https://github.com/holland202/sovereign-veritas/blob/main/docs/EXECUTION_BOUNDARY_PREREG.md)
- [`tools/execution_boundary_probe.py`](https://github.com/holland202/sovereign-veritas/blob/main/tools/execution_boundary_probe.py)

Materials accessed 18 October 2026. Comments refer to the versions reviewed on that date.
