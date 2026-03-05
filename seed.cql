// ============================================
// Ontology Marketplace — Full Seed Data
// ============================================
// Recreates the complete Neo4j database with:
//   - Users, Ontologies, Tags (existing app)
//   - Comments, Replies, Reactions (community feature)
//   - Flags (content moderation)
//   - Admin Messages (admin-to-user messaging)
//
// Usage:
//   1. Clear the database first:  MATCH (n) DETACH DELETE n;
//   2. Run this file in Neo4j Browser or via cypher-shell
//   3. Run the indexes section separately if needed

// ============================================
// Indexes & Constraints
// ============================================

CREATE INDEX ontology_uuid IF NOT EXISTS FOR (o:Ontology) ON (o.uuid);
CREATE INDEX user_fuid IF NOT EXISTS FOR (u:User) ON (u.fuid);
CREATE INDEX comment_uuid IF NOT EXISTS FOR (c:Comment) ON (c.uuid);
CREATE INDEX message_uuid IF NOT EXISTS FOR (m:Message) ON (m.uuid);
CREATE INDEX reaction_uuid IF NOT EXISTS FOR (r:Reaction) ON (r.uuid);
CREATE INDEX flag_uuid IF NOT EXISTS FOR (f:Flag) ON (f.uuid);
CREATE INDEX resource_uri IF NOT EXISTS FOR (n:Resource) ON (n.uri);
CREATE INDEX tag_name IF NOT EXISTS FOR (t:Tag) ON (t.name);

// ============================================
// Users
// ============================================

CREATE (u1:User {
  fuid: 'firebase-uid-001',
  uuid: 'user-uuid-001',
  email: 'alice@example.com',
  is_public: true,
  is_admin: true,
  created_at: datetime('2025-01-01T10:00:00Z')
})

CREATE (u2:User {
  fuid: 'firebase-uid-002',
  uuid: 'user-uuid-002',
  email: 'bob@example.com',
  is_public: true,
  is_admin: false,
  created_at: datetime('2025-01-02T10:00:00Z')
})

CREATE (u3:User {
  fuid: 'firebase-uid-003',
  uuid: 'user-uuid-003',
  email: 'carol@example.com',
  is_public: false,
  is_admin: false,
  created_at: datetime('2025-01-03T10:00:00Z')
})

CREATE (u4:User {
  fuid: 'firebase-uid-004',
  uuid: 'user-uuid-004',
  email: 'admin@ontologymarketplace.com',
  is_public: true,
  is_admin: true,
  created_at: datetime('2025-01-01T08:00:00Z')
});

// ============================================
// Tags
// ============================================

CREATE (tag1:Tag { name: 'medical' })
CREATE (tag2:Tag { name: 'healthcare' })
CREATE (tag3:Tag { name: 'products' })
CREATE (tag4:Tag { name: 'business' })
CREATE (tag5:Tag { name: 'finance' })
CREATE (tag6:Tag { name: 'research' })
CREATE (tag7:Tag { name: 'journalism' })
CREATE (tag8:Tag { name: 'politics' })
CREATE (tag9:Tag { name: 'education' })
CREATE (tag10:Tag { name: 'technology' });

// ============================================
// Ontologies
// ============================================

// 1. Medical Disease Ontology (public, owned by alice)
CREATE (ont1:Ontology {
  uuid: 'ont-uuid-001',
  name: 'Medical Disease Ontology',
  description: 'Comprehensive ontology for diseases, symptoms, and treatments. Includes relationships between medical conditions and their characteristics.',
  source_url: 'https://example.com/medical-ontology.owl',
  image_url: 'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=400',
  is_public: true,
  node_count: 45,
  relationship_count: 120,
  created_at: datetime('2025-01-10T08:00:00Z'),
  updated_time: datetime('2025-01-15T14:30:00Z')
})

// 2. E-commerce Product Ontology (public, owned by bob)
CREATE (ont2:Ontology {
  uuid: 'ont-uuid-002',
  name: 'E-commerce Product Ontology',
  description: 'Product classification, categories, and commerce relationships for online retail. Includes pricing, inventory, and review structures.',
  source_url: 'https://example.com/ecommerce.owl',
  image_url: 'https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400',
  is_public: true,
  node_count: 38,
  relationship_count: 95,
  created_at: datetime('2025-01-08T09:15:00Z'),
  updated_time: datetime('2025-01-12T16:45:00Z')
})

// 3. Financial Services Ontology (private, owned by alice)
CREATE (ont3:Ontology {
  uuid: 'ont-uuid-003',
  name: 'Financial Services Ontology',
  description: 'Banking, transactions, accounts, and financial instruments modeling. Covers banking operations, account types, and transaction flows.',
  source_url: 'https://example.com/finance.owl',
  image_url: 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=400',
  is_public: false,
  node_count: 52,
  relationship_count: 138,
  created_at: datetime('2025-01-05T11:00:00Z'),
  updated_time: datetime('2025-01-14T10:20:00Z')
})

// 4. Education Ontology (public, owned by carol)
CREATE (ont4:Ontology {
  uuid: 'ont-uuid-004',
  name: 'Higher Education Ontology',
  description: 'Models universities, courses, departments, and academic relationships for educational institution management.',
  source_url: 'https://example.com/education.owl',
  image_url: 'https://images.unsplash.com/photo-1523050854058-8df90110c476?w=400',
  is_public: true,
  node_count: 30,
  relationship_count: 72,
  created_at: datetime('2025-01-20T13:00:00Z'),
  updated_time: datetime('2025-01-22T09:10:00Z')
});

// ============================================
// User → Ontology Relationships
// ============================================

// alice created ont1 and ont3
MATCH (u:User {fuid: 'firebase-uid-001'}), (o:Ontology {uuid: 'ont-uuid-001'})
CREATE (u)-[:CREATED]->(o)
CREATE (u)-[:CAN_EDIT]->(o)
CREATE (u)-[:CAN_DELETE]->(o);

MATCH (u:User {fuid: 'firebase-uid-001'}), (o:Ontology {uuid: 'ont-uuid-003'})
CREATE (u)-[:CREATED]->(o)
CREATE (u)-[:CAN_EDIT]->(o)
CREATE (u)-[:CAN_DELETE]->(o);

// bob created ont2
MATCH (u:User {fuid: 'firebase-uid-002'}), (o:Ontology {uuid: 'ont-uuid-002'})
CREATE (u)-[:CREATED]->(o)
CREATE (u)-[:CAN_EDIT]->(o)
CREATE (u)-[:CAN_DELETE]->(o);

// carol created ont4
MATCH (u:User {fuid: 'firebase-uid-003'}), (o:Ontology {uuid: 'ont-uuid-004'})
CREATE (u)-[:CREATED]->(o)
CREATE (u)-[:CAN_EDIT]->(o)
CREATE (u)-[:CAN_DELETE]->(o);

// bob can also edit alice's medical ontology (collaborator)
MATCH (u:User {fuid: 'firebase-uid-002'}), (o:Ontology {uuid: 'ont-uuid-001'})
CREATE (u)-[:CAN_EDIT]->(o);

// ============================================
// Ontology → Tag Relationships
// ============================================

MATCH (o:Ontology {uuid: 'ont-uuid-001'}), (t:Tag {name: 'medical'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-001'}), (t:Tag {name: 'healthcare'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-001'}), (t:Tag {name: 'research'})
CREATE (o)-[:TAGGED]->(t);

MATCH (o:Ontology {uuid: 'ont-uuid-002'}), (t:Tag {name: 'products'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-002'}), (t:Tag {name: 'business'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-002'}), (t:Tag {name: 'technology'})
CREATE (o)-[:TAGGED]->(t);

MATCH (o:Ontology {uuid: 'ont-uuid-003'}), (t:Tag {name: 'finance'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-003'}), (t:Tag {name: 'business'})
CREATE (o)-[:TAGGED]->(t);

MATCH (o:Ontology {uuid: 'ont-uuid-004'}), (t:Tag {name: 'education'})
CREATE (o)-[:TAGGED]->(t);
MATCH (o:Ontology {uuid: 'ont-uuid-004'}), (t:Tag {name: 'research'})
CREATE (o)-[:TAGGED]->(t);

// ============================================
// Comments on Ontologies
// ============================================

// Comment 1: bob comments on the medical ontology
MATCH (u:User {fuid: 'firebase-uid-002'}), (o:Ontology {uuid: 'ont-uuid-001'})
CREATE (c1:Comment {
  uuid: 'comment-uuid-001',
  content: 'Great ontology! The disease-symptom relationships are very well structured. Would love to see treatment protocols added.',
  created_at: datetime('2025-01-16T09:30:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(c1)
CREATE (c1)-[:COMMENTED_ON]->(o);

// Comment 2: carol comments on the medical ontology
MATCH (u:User {fuid: 'firebase-uid-003'}), (o:Ontology {uuid: 'ont-uuid-001'})
CREATE (c2:Comment {
  uuid: 'comment-uuid-002',
  content: 'I am using this in my research project on epidemiological modeling. The node structure maps perfectly to our data.',
  created_at: datetime('2025-01-17T14:15:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(c2)
CREATE (c2)-[:COMMENTED_ON]->(o);

// Comment 3: alice comments on bob's e-commerce ontology
MATCH (u:User {fuid: 'firebase-uid-001'}), (o:Ontology {uuid: 'ont-uuid-002'})
CREATE (c3:Comment {
  uuid: 'comment-uuid-003',
  content: 'Nice work on the product categorization. How do you handle multi-category products?',
  created_at: datetime('2025-01-13T11:00:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(c3)
CREATE (c3)-[:COMMENTED_ON]->(o);

// Comment 4: carol comments on the education ontology (her own)
MATCH (u:User {fuid: 'firebase-uid-003'}), (o:Ontology {uuid: 'ont-uuid-004'})
CREATE (c4:Comment {
  uuid: 'comment-uuid-004',
  content: 'Updated this ontology to include the latest department restructuring from our university.',
  created_at: datetime('2025-01-22T10:00:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(c4)
CREATE (c4)-[:COMMENTED_ON]->(o);

// Comment 5: bob comments on the education ontology
MATCH (u:User {fuid: 'firebase-uid-002'}), (o:Ontology {uuid: 'ont-uuid-004'})
CREATE (c5:Comment {
  uuid: 'comment-uuid-005',
  content: 'Could this be extended to model online learning platforms and MOOCs?',
  created_at: datetime('2025-01-23T15:30:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(c5)
CREATE (c5)-[:COMMENTED_ON]->(o);

// ============================================
// Replies to Comments
// ============================================

// alice replies to bob's comment on her medical ontology
MATCH (u:User {fuid: 'firebase-uid-001'}), (parent:Comment {uuid: 'comment-uuid-001'}),
      (o:Ontology {uuid: 'ont-uuid-001'})
CREATE (reply1:Comment {
  uuid: 'comment-uuid-006',
  content: 'Thanks Bob! Treatment protocols are on the roadmap. Hoping to add them next month.',
  created_at: datetime('2025-01-16T10:45:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(reply1)
CREATE (reply1)-[:REPLY_TO]->(parent)
CREATE (reply1)-[:COMMENTED_ON]->(o);

// bob replies to alice's comment on his e-commerce ontology
MATCH (u:User {fuid: 'firebase-uid-002'}), (parent:Comment {uuid: 'comment-uuid-003'}),
      (o:Ontology {uuid: 'ont-uuid-002'})
CREATE (reply2:Comment {
  uuid: 'comment-uuid-007',
  content: 'Good question! We use a BELONGS_TO relationship with a primary flag. Each product can belong to multiple categories but has one primary.',
  created_at: datetime('2025-01-13T14:20:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(reply2)
CREATE (reply2)-[:REPLY_TO]->(parent)
CREATE (reply2)-[:COMMENTED_ON]->(o);

// carol replies to bob's question on her education ontology
MATCH (u:User {fuid: 'firebase-uid-003'}), (parent:Comment {uuid: 'comment-uuid-005'}),
      (o:Ontology {uuid: 'ont-uuid-004'})
CREATE (reply3:Comment {
  uuid: 'comment-uuid-008',
  content: 'Absolutely! I have been thinking about adding an OnlineCourse subclass. Want to collaborate?',
  created_at: datetime('2025-01-24T09:00:00Z'),
  is_deleted: false,
  updated_at: null
})
CREATE (u)-[:AUTHORED]->(reply3)
CREATE (reply3)-[:REPLY_TO]->(parent)
CREATE (reply3)-[:COMMENTED_ON]->(o);

// ============================================
// Reactions on Comments
// ============================================

// Reactions on comment 1 (bob's comment on medical ontology)
MATCH (u1:User {fuid: 'firebase-uid-001'}), (c:Comment {uuid: 'comment-uuid-001'})
CREATE (r1:Reaction { uuid: 'reaction-uuid-001', emoji: '👍', created_at: datetime('2025-01-16T09:35:00Z') })
CREATE (c)-[:HAS_REACTION]->(r1)
CREATE (r1)-[:REACTION_BY]->(u1);

MATCH (u3:User {fuid: 'firebase-uid-003'}), (c:Comment {uuid: 'comment-uuid-001'})
CREATE (r2:Reaction { uuid: 'reaction-uuid-002', emoji: '👍', created_at: datetime('2025-01-17T14:20:00Z') })
CREATE (c)-[:HAS_REACTION]->(r2)
CREATE (r2)-[:REACTION_BY]->(u3);

MATCH (u3:User {fuid: 'firebase-uid-003'}), (c:Comment {uuid: 'comment-uuid-001'})
CREATE (r3:Reaction { uuid: 'reaction-uuid-003', emoji: '❤️', created_at: datetime('2025-01-17T14:21:00Z') })
CREATE (c)-[:HAS_REACTION]->(r3)
CREATE (r3)-[:REACTION_BY]->(u3);

// Reactions on comment 2 (carol's comment on medical ontology)
MATCH (u1:User {fuid: 'firebase-uid-001'}), (c:Comment {uuid: 'comment-uuid-002'})
CREATE (r4:Reaction { uuid: 'reaction-uuid-004', emoji: '🎉', created_at: datetime('2025-01-17T15:00:00Z') })
CREATE (c)-[:HAS_REACTION]->(r4)
CREATE (r4)-[:REACTION_BY]->(u1);

MATCH (u2:User {fuid: 'firebase-uid-002'}), (c:Comment {uuid: 'comment-uuid-002'})
CREATE (r5:Reaction { uuid: 'reaction-uuid-005', emoji: '🔥', created_at: datetime('2025-01-17T16:00:00Z') })
CREATE (c)-[:HAS_REACTION]->(r5)
CREATE (r5)-[:REACTION_BY]->(u2);

// Reactions on reply 1 (alice's reply to bob)
MATCH (u2:User {fuid: 'firebase-uid-002'}), (c:Comment {uuid: 'comment-uuid-006'})
CREATE (r6:Reaction { uuid: 'reaction-uuid-006', emoji: '👍', created_at: datetime('2025-01-16T11:00:00Z') })
CREATE (c)-[:HAS_REACTION]->(r6)
CREATE (r6)-[:REACTION_BY]->(u2);

// Reactions on comment 3 (alice's comment on e-commerce ontology)
MATCH (u2:User {fuid: 'firebase-uid-002'}), (c:Comment {uuid: 'comment-uuid-003'})
CREATE (r7:Reaction { uuid: 'reaction-uuid-007', emoji: '❤️', created_at: datetime('2025-01-13T11:30:00Z') })
CREATE (c)-[:HAS_REACTION]->(r7)
CREATE (r7)-[:REACTION_BY]->(u2);

// Reactions on reply 3 (carol's reply about collaboration)
MATCH (u2:User {fuid: 'firebase-uid-002'}), (c:Comment {uuid: 'comment-uuid-008'})
CREATE (r8:Reaction { uuid: 'reaction-uuid-008', emoji: '🎉', created_at: datetime('2025-01-24T09:30:00Z') })
CREATE (c)-[:HAS_REACTION]->(r8)
CREATE (r8)-[:REACTION_BY]->(u2);

MATCH (u1:User {fuid: 'firebase-uid-001'}), (c:Comment {uuid: 'comment-uuid-008'})
CREATE (r9:Reaction { uuid: 'reaction-uuid-009', emoji: '👍', created_at: datetime('2025-01-24T10:00:00Z') })
CREATE (c)-[:HAS_REACTION]->(r9)
CREATE (r9)-[:REACTION_BY]->(u1);

// ============================================
// Admin Messages
// ============================================

// Admin (alice) sends a welcome message to bob
MATCH (sender:User {fuid: 'firebase-uid-001'}), (recipient:User {fuid: 'firebase-uid-002'})
CREATE (m1:Message {
  uuid: 'message-uuid-001',
  subject: 'Welcome to Ontology Marketplace',
  content: 'Hi Bob, welcome to the platform! Feel free to reach out if you have any questions about uploading or managing ontologies.',
  is_read: true,
  created_at: datetime('2025-01-02T12:00:00Z')
})
CREATE (sender)-[:SENT_MESSAGE]->(m1)
CREATE (m1)-[:RECEIVED_MESSAGE]->(recipient);

// bob replies to the welcome message
MATCH (sender:User {fuid: 'firebase-uid-002'}), (recipient:User {fuid: 'firebase-uid-001'}),
      (parent:Message {uuid: 'message-uuid-001'})
CREATE (m2:Message {
  uuid: 'message-uuid-002',
  subject: 'Re: Welcome to Ontology Marketplace',
  content: 'Thanks Alice! Quick question - is there a size limit on ontology files for upload?',
  is_read: true,
  created_at: datetime('2025-01-02T14:30:00Z')
})
CREATE (sender)-[:SENT_MESSAGE]->(m2)
CREATE (m2)-[:RECEIVED_MESSAGE]->(recipient)
CREATE (m2)-[:REPLY_TO_MESSAGE]->(parent);

// Admin (alice) replies back
MATCH (sender:User {fuid: 'firebase-uid-001'}), (recipient:User {fuid: 'firebase-uid-002'}),
      (parent:Message {uuid: 'message-uuid-002'})
CREATE (m3:Message {
  uuid: 'message-uuid-003',
  subject: 'Re: Welcome to Ontology Marketplace',
  content: 'No hard limit currently, but we recommend keeping files under 50MB for best performance. Larger ontologies can be split into modules.',
  is_read: false,
  created_at: datetime('2025-01-03T09:00:00Z')
})
CREATE (sender)-[:SENT_MESSAGE]->(m3)
CREATE (m3)-[:RECEIVED_MESSAGE]->(recipient)
CREATE (m3)-[:REPLY_TO_MESSAGE]->(parent);

// Admin (u4) sends a policy update to carol
MATCH (sender:User {fuid: 'firebase-uid-004'}), (recipient:User {fuid: 'firebase-uid-003'})
CREATE (m4:Message {
  uuid: 'message-uuid-004',
  subject: 'New Community Guidelines',
  content: 'Hi Carol, we have updated our community guidelines regarding ontology sharing and comments. Please review the updated terms at your convenience.',
  is_read: false,
  created_at: datetime('2025-01-25T08:00:00Z')
})
CREATE (sender)-[:SENT_MESSAGE]->(m4)
CREATE (m4)-[:RECEIVED_MESSAGE]->(recipient);

// Admin (u4) sends a feature announcement to bob
MATCH (sender:User {fuid: 'firebase-uid-004'}), (recipient:User {fuid: 'firebase-uid-002'})
CREATE (m5:Message {
  uuid: 'message-uuid-005',
  subject: 'New Feature: Ontology Comments',
  content: 'Hi Bob, we just launched comments on ontologies! You can now discuss and collaborate with other users directly on ontology pages.',
  is_read: false,
  created_at: datetime('2025-01-26T10:00:00Z')
})
CREATE (sender)-[:SENT_MESSAGE]->(m5)
CREATE (m5)-[:RECEIVED_MESSAGE]->(recipient);

// ============================================
// Flags (Content Moderation)
// ============================================

// carol flags bob's comment on the medical ontology as off-topic
MATCH (flagger:User {fuid: 'firebase-uid-003'}), (c:Comment {uuid: 'comment-uuid-001'})
CREATE (f1:Flag {
  uuid: 'flag-uuid-001',
  reason: 'off_topic',
  details: null,
  status: 'pending',
  created_at: datetime('2025-01-18T10:00:00Z'),
  reviewed_at: null
})
CREATE (f1)-[:FLAGGED_BY]->(flagger)
CREATE (f1)-[:FLAGGED_CONTENT]->(c);

// bob flags carol's comment on the education ontology as spam
MATCH (flagger:User {fuid: 'firebase-uid-002'}), (c:Comment {uuid: 'comment-uuid-004'})
CREATE (f2:Flag {
  uuid: 'flag-uuid-002',
  reason: 'spam',
  details: 'This looks like a self-promotional update, not a discussion comment.',
  status: 'pending',
  created_at: datetime('2025-01-23T08:00:00Z'),
  reviewed_at: null
})
CREATE (f2)-[:FLAGGED_BY]->(flagger)
CREATE (f2)-[:FLAGGED_CONTENT]->(c);

// alice flags bob's reply on the e-commerce ontology (already reviewed/dismissed by admin)
MATCH (flagger:User {fuid: 'firebase-uid-001'}), (c:Comment {uuid: 'comment-uuid-007'}),
      (admin:User {fuid: 'firebase-uid-004'})
CREATE (f3:Flag {
  uuid: 'flag-uuid-003',
  reason: 'other',
  details: 'This reply contains potentially inaccurate technical information about the schema.',
  status: 'dismissed',
  created_at: datetime('2025-01-14T09:00:00Z'),
  reviewed_at: datetime('2025-01-14T16:00:00Z')
})
CREATE (f3)-[:FLAGGED_BY]->(flagger)
CREATE (f3)-[:FLAGGED_CONTENT]->(c)
CREATE (f3)-[:REVIEWED_BY]->(admin);

// ============================================
// Verification Queries
// ============================================

// Count all node types
// MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label;

// List ontologies with their owners and tags
// MATCH (u:User)-[:CREATED]->(o:Ontology)
// OPTIONAL MATCH (o)-[:TAGGED]->(t:Tag)
// RETURN o.name, u.email AS owner, collect(t.name) AS tags, o.is_public;

// List comments with authors and ontology context
// MATCH (u:User)-[:AUTHORED]->(c:Comment)-[:COMMENTED_ON]->(o:Ontology)
// OPTIONAL MATCH (c)-[:REPLY_TO]->(parent:Comment)
// RETURN u.email AS author, c.content, o.name AS ontology,
//        parent.uuid AS reply_to, c.created_at
// ORDER BY c.created_at;

// List reactions grouped by comment
// MATCH (c:Comment)<-[:COMMENTED_ON*0..1]-(c2:Comment)-[:HAS_REACTION]->(r:Reaction)-[:REACTION_BY]->(u:User)
// WITH c2, r.emoji AS emoji, collect(u.email) AS users
// RETURN c2.uuid, c2.content, emoji, users;

// List messages with sender/recipient
// MATCH (sender:User)-[:SENT_MESSAGE]->(m:Message)-[:RECEIVED_MESSAGE]->(recipient:User)
// OPTIONAL MATCH (m)-[:REPLY_TO_MESSAGE]->(parent:Message)
// RETURN sender.email AS from, recipient.email AS to,
//        m.subject, m.is_read, parent.uuid AS reply_to, m.created_at
// ORDER BY m.created_at;

// Count unread messages per user
// MATCH (m:Message {is_read: false})-[:RECEIVED_MESSAGE]->(u:User)
// RETURN u.email, count(m) AS unread;

// Get full comment thread for an ontology
// MATCH (c:Comment)-[:COMMENTED_ON]->(o:Ontology {uuid: 'ont-uuid-001'})
// MATCH (u:User)-[:AUTHORED]->(c)
// OPTIONAL MATCH (c)-[:REPLY_TO]->(parent:Comment)
// OPTIONAL MATCH (c)-[:HAS_REACTION]->(r:Reaction)
// WITH c, u, parent, collect(r.emoji) AS reactions
// RETURN c.uuid, u.email AS author, c.content, parent.uuid AS reply_to,
//        reactions, c.created_at
// ORDER BY c.created_at;

// List all flags with status
// MATCH (f:Flag)-[:FLAGGED_CONTENT]->(c:Comment)-[:COMMENTED_ON]->(o:Ontology)
// MATCH (f)-[:FLAGGED_BY]->(flagger:User)
// MATCH (author:User)-[:AUTHORED]->(c)
// OPTIONAL MATCH (f)-[:REVIEWED_BY]->(reviewer:User)
// RETURN f.uuid, f.reason, f.details, f.status,
//        flagger.email AS flagged_by, author.email AS comment_author,
//        c.content AS comment_content, o.name AS ontology,
//        reviewer.email AS reviewed_by, f.created_at, f.reviewed_at
// ORDER BY f.created_at;

// Count pending flags
// MATCH (f:Flag {status: 'pending'})
// RETURN count(f) AS pending_flags;
