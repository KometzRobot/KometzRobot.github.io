# Brothers Fabrication — Project Bible
## Joel Kometz | Tech Services & AI Integration
### Version 1.0 — April 16, 2026

---

## 1. Executive Summary

Brothers Fabrication (Calgary, AB) needs a modern tech stack: professional website, job/material database, local AI assistant, and managed IT services. Joel Kometz delivers the full package — from design to deployment to ongoing support.

**Client:** Chris Kometz, Brothers Fabrication
**Contractor:** Joel Kometz
**Relationship:** Brothers — 30% discount from market rate
**Total Project:** $45,000-50,000 + $1,200-1,500/month retainer
**Timeline:** 3-6 months phased delivery
**Potential:** Partnership/equity in Brothers Fabrication; productize for other shops

---

## 2. Current State (What They Have)

- **Devices:** macOS desktops (office), workstation + audio/mic (shop floor)
- **Project Management:** Trello (keep — don't replace what works)
- **File Storage:** Ad hoc (USB sticks, email attachments)
- **Website:** None or outdated
- **AI:** None
- **IT Services:** None (no antivirus, no backups, no monitoring)

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────┐
│              BROTHERS FABRICATION            │
│                                             │
│  ┌─────────┐  ┌─────────┐  ┌────────────┐  │
│  │  Macs   │  │ Tablet  │  │  Server    │  │
│  │ (office)│  │ (shop)  │  │ (closet)   │  │
│  └────┬────┘  └────┬────┘  └─────┬──────┘  │
│       │            │              │         │
│       └────────────┼──────────────┘         │
│                    │                        │
│              Local Network                  │
│       ┌────────────┼──────────────┐         │
│       │            │              │         │
│  ┌────┴────┐ ┌─────┴─────┐ ┌─────┴──────┐  │
│  │Synology │ │  Ollama   │ │ AnythingLLM│  │
│  │  NAS    │ │  (AI)     │ │  (Chat UI) │  │
│  │(files)  │ │           │ │            │  │
│  └─────────┘ └───────────┘ └────────────┘  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │         Supabase (Database)         │    │
│  │  Jobs | Clients | Materials | Quotes│    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │         Website (Next.js)           │    │
│  │  About | Services | Gallery | Quote │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 4. Phase Breakdown

### Phase 1: AI + Server Setup ($2,000)
**Duration:** 1 weekend + 1 week testing
**Deliverables:**
- [ ] Server hardware procured and set up (mini PC, Ubuntu)
- [ ] Ollama installed with 3B (fast) and 7B (smart) models
- [ ] AnythingLLM installed, branded as "Brothers AI"
- [ ] Initial document upload (quotes, specs, procedures)
- [ ] Android tablet procured, wall-mounted, kiosk mode configured
- [ ] Voice input enabled on tablet
- [ ] 2-hour training session with Chris
- [ ] Documentation: quick start guide for shop workers

### Phase 2: Database + Dashboard ($2,500)
**Duration:** 1-2 weeks
**Deliverables:**
- [ ] Supabase project created
- [ ] Database tables: jobs, clients, materials, quotes
- [ ] Admin dashboard (job status, client lookup, material tracking)
- [ ] AI agent integration (queries database, not just documents)
- [ ] Data import from existing spreadsheets/Trello exports
- [ ] Weekly automated reports (email to Chris every Monday 6 AM)
- [ ] Material low-stock alerts

### Phase 3: Website ($2,000)
**Duration:** 1-2 weeks
**Deliverables:**
- [ ] Professional website (Next.js or WordPress)
- [ ] Pages: About, Services, Gallery, Quote Request, Contact
- [ ] Quote request form writes to Supabase
- [ ] Project gallery with job photos
- [ ] Mobile responsive
- [ ] SEO basics: Google Business Profile, local search optimization
- [ ] SSL certificate, professional domain

### Phase 4: IT Services Setup ($1,500)
**Duration:** 1 day setup + ongoing
**Deliverables:**
- [ ] Synology NAS (2-bay, ~$400 hardware — client pays)
- [ ] Shared folders configured with permissions
- [ ] Endpoint protection on all devices (CrowdStrike Falcon Go or Bitdefender)
- [ ] Automated daily backups (NAS + weekly offsite)
- [ ] Remote monitoring installed (Tactical RMM)
- [ ] Remote access configured (RustDesk)
- [ ] Documentation: IT services overview for Chris

### Ongoing: Monthly Retainer ($1,200-1,500/month)
- AI maintenance (adding documents, updating models)
- IT monitoring (weekly dashboard check)
- Backup verification
- Security updates
- Remote troubleshooting
- Monthly check-in (30 min call or visit)
- Feature requests and improvements
- Priority support

---

## 5. Hardware Shopping List

| Item | Est. Cost (CAD) | Who Pays |
|------|-----------------|----------|
| Mini PC (Beelink/NUC, 16GB RAM, 512GB SSD) | $400-600 | Client |
| Android Tablet (10-11", wall mount) | $250-350 | Client |
| Tablet Wall Mount Bracket | $30-50 | Client |
| Synology DS224+ NAS | $400-500 | Client |
| 2x 4TB NAS drives (Seagate IronWolf) | $250-300 | Client |
| Ethernet cables, switch if needed | $50-100 | Client |
| **Total Hardware** | **$1,380-1,900** | **Client** |

---

## 6. Software Stack (All Free/Open Source)

| Software | Purpose | License | Cost |
|----------|---------|---------|------|
| Ubuntu Server 24.04 | Server OS | Free | $0 |
| Ollama | AI model runtime | MIT | $0 |
| AnythingLLM | Chat interface + RAG | MIT | $0 |
| Supabase | Database + API + Auth | Apache 2.0 | $0 (self-hosted) or free tier |
| Next.js | Website framework | MIT | $0 |
| Tactical RMM | Remote monitoring | Free | $0 (self-hosted) |
| RustDesk | Remote access | AGPL | $0 (self-hosted) |
| CrowdStrike Falcon Go | Endpoint protection | Commercial | ~$5/device/month |
| Fully Kiosk Browser | Tablet kiosk mode | Commercial | $7 one-time |

---

## 7. Clever Features (Differentiators)

- **Voice Commands:** "Hey, what's the status of the Johnson job?" — hands-free on shop floor
- **Photo Logging:** Workers snap a photo, AI tags it to the active job
- **Material Alerts:** "Low on 3/4 plate — last 3 orders averaged 2 weeks delivery"
- **End-of-Day Summary:** Auto-generated daily log emailed to Chris
- **Client Portal:** Clients check job status online (read-only view)
- **Dual Model Architecture:** 3B model for fast shop-floor queries, 7B for complex reasoning

---

## 8. Pricing Summary

| Component | Market Rate | Joel's Rate (30% off) |
|-----------|------------|----------------------|
| Phase 1: AI + Server | $6,000-8,000 | $2,000 |
| Phase 2: Database | $10,000-15,000 | $2,500 |
| Phase 3: Website | $5,000-10,000 | $2,000 |
| Phase 4: IT Setup | $3,000-5,000 | $1,500 |
| **Total Project** | **$24,000-38,000** | **$8,000** |
| Monthly Retainer | $500-2,000/mo | $1,200-1,500/mo |

**Note:** Joel's initial rate reflects family pricing and first-client portfolio building. Second client and beyond: price at 80-100% of market rate.

---

## 9. Productization Roadmap

After Brothers Fabrication is running:
1. **Document everything** — screenshots, architecture, process notes
2. **Create a case study** — "Brothers Fabrication runs on this"
3. **Brand it** — "ShopAI" or similar name for the productized version
4. **Target market** — welding shops, machine shops, fabrication shops in Calgary/Alberta
5. **Pricing for new clients** — $15,000-25,000 setup + $500-1,500/month
6. **Scale** — 5 clients = $2,500-7,500/month recurring revenue

---

## 10. Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Chris expects too much too fast | Phased delivery with clear milestones |
| AI gives wrong answers | RAG over verified documents only; disclaimers |
| Hardware failure | Automated backups; NAS RAID; remote monitoring alerts |
| Scope creep | Written agreement with defined phases; changes = new quotes |
| Joel gets overwhelmed | Prioritize by phase; don't start phase N+1 until N is signed off |
| Family tension over money | Written agreement; professional communication; regular check-ins |

---

## 11. Agreement Template (Simple)

**Between:** Joel Kometz ("Contractor") and Brothers Fabrication ("Client")

**Scope:** Technology services as described in Phases 1-4 above.

**Payment Schedule:**
- Phase 1 complete: $X
- Phase 2 complete: $X
- Phase 3 complete: $X
- Phase 4 complete: $X
- Monthly retainer begins after Phase 1 delivery: $X/month

**Ownership:** Client owns all data. Contractor retains right to use the architecture/design for other clients (no client data shared).

**Partnership:** [To be discussed — equity %, dividends, terms]

**Changes:** Any work outside defined scope requires written approval and separate quote.

**Termination:** Either party with 30 days notice. Client keeps all delivered work and data.

---

*Written by Meridian for Joel Kometz. April 16, 2026.*
*"Brothers Fabrication runs on this. Your shop can too."*
