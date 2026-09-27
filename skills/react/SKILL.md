# ReAct Skill

Purpose: decide whether a missing current-case fact must be provided by the engineer before recommendation.

Cycle: Reason -> decide whether clarification is required -> if yes, interrupt for the engineer response -> re-understand the updated conversation.

Allowed outcomes:
- require clarification from the engineer
- proceed to recommendation

Do not request another internal search or another external search. The Planner has already selected the research path, and the specialist workers have already gathered the planned evidence.

When clarification is required, ask one focused question that can only be answered by the engineer's current incident context.
