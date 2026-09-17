// Equivalent of careen-blocks-trice-assigned-contact.graph.json
// Careen project --blocks--> Trice task --assignedToContact--> Yeoman contact
// Stage-gate family siblings of blocks: blocked_by, depends_on
MATCH (careen {id: 'urn:careen:project:018f3a00-0000-7000-8000-000000000009'})
      -[:blocks]->(trice {id: 'urn:trice:task:018f3a00-0000-7000-8000-000000000003'})
      -[:assignedToContact]->(yeoman {id: 'urn:yeoman:contact:018f3a00-0000-7000-8000-000000000002'})
RETURN careen, trice, yeoman
