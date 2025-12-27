# Planning Guide

A centralized, accessible platform for discovering, reviewing, and discussing assistive technology and accessibility products where users can rate, tag, and engage in community discussions.

**Architecture**: REST-based API
The application uses a REST API architecture where all data operations are performed through HTTP requests to RESTful endpoints. The frontend communicates with a mock REST API layer that provides standard HTTP methods (GET, POST, PATCH, DELETE) for all resource operations. This architecture provides clear separation of concerns, predictable URL patterns, and standardized request/response handling.

**Experience Qualities**:
1. **Inclusive**: Every interaction prioritizes keyboard navigation, screen reader support, and WCAG AA compliance to ensure the platform practices what it promotes
2. **Community-Driven**: Foster meaningful engagement through ratings, reviews, tags, and threaded discussions that help users make informed decisions
3. **Discoverable**: Intelligent search, filtering, and tagging systems that surface relevant products quickly and intuitively

**Complexity Level**: Complex Application (advanced functionality, likely with multiple views)
This application requires multiple interconnected features - product browsing with filtering/search, individual product detail pages with ratings/reviews/tags, discussion threads with replies, and persistent data management across all these systems. The data relationships between products, reviews, ratings, tags, and discussions necessitate sophisticated state management.
