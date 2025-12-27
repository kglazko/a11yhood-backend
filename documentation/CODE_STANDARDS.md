# Code Standards and Best Practices

This document outlines the coding standards, patterns, and best practices for the a11yhood codebase.

## Table of Contents
1. [General Principles](#general-principles)
2. [TypeScript Guidelines](#typescript-guidelines)
3. [React Patterns](#react-patterns)
4. [State Management](#state-management)
5. [API and Data Access](#api-and-data-access)
6. [Error Handling](#error-handling)
7. [Testing Standards](#testing-standards)
8. [Accessibility](#accessibility)
9. [Documentation](#documentation)

---

## General Principles

### Code Quality Tenets

1. **Readability First**: Code is read far more often than written
2. **Type Safety**: Leverage TypeScript's type system fully
3. **Testability**: Write code that's easy to test
4. **Performance**: Optimize for user experience, not premature optimization

## API and Data Access

### API Service Pattern

```typescript
// ✅ GOOD: Typed request/response
export class APIService {
  /**
   * Fetches all products from the database
   * @returns Array of products
   * @throws {APIError} If the request fails
   */
  static async getAllProducts(): Promise<Product[]> {
    return request<Product[]>('/products')
  }
  
  /**
   * Updates a product with change tracking
   * @param productId - ID of product to update
   * @param updates - Partial product data
   * @param editorId - User ID of editor (optional)
   * @returns Updated product or null if not found
   * @throws {APIError} If the update fails
   */
  static async updateProduct(
    productId: string,
    updates: Partial<Product>,
    editorId?: string
  ): Promise<Product | null> {
    return request<Product | null>(`/products/${productId}`, {
      method: 'PATCH',
      body: JSON.stringify({ updates, editorId }),
    })
  }
}
```

### Error Handling in API Calls

```typescript
// ✅ GOOD: Comprehensive error handling
async function loadProducts() {
  try {
    setIsLoading(true)
    setError(null)
    
    const products = await APIService.getAllProducts()
    setProducts(products)
    
  } catch (error) {
    console.error('Failed to load products:', error)
    
    if (error instanceof APIError) {
      if (error.status === 404) {
        setError('Products not found')
      } else if (error.status >= 500) {
        setError('Server error. Please try again later.')
      } else {
        setError(error.message)
      }
    } else {
      setError('An unexpected error occurred')
    }
    
    toast.error('Failed to load products')
    
  } finally {
    setIsLoading(false)
  }
}
```

### Database Service Pattern

```typescript
// ✅ GOOD: Clear separation of concerns
export class DatabaseService {
  private static readonly KEYS = {
    PRODUCTS: 'products',
    USERS: 'users',
  }
  
  /**
   * Retrieves all products from KV store
   * @returns Array of products (empty array if none exist)
   */
  static async getAllProducts(): Promise<Product[]> {
    const products = await window.spark.kv.get<Product[]>(this.KEYS.PRODUCTS)
    return products || []
  }
  
  /**
   * Saves products to KV store with automatic normalization
   * Ensures all products have proper origin tracking
   * @param products - Array of products to save
   */
  static async saveProducts(products: Product[]): Promise<void> {
    const normalized = products.map(p => ({
      ...p,
      origin: p.origin || this.deriveOrigin(p)
    }))
    
    await window.spark.kv.set(this.KEYS.PRODUCTS, normalized)
  }
  
  /**
   * Derives product origin from source field
   * @private
   */
  private static deriveOrigin(product: Product): Product['origin'] {
    const source = product.source?.toLowerCase() || ''
    
    if (source.includes('thingiverse')) return 'scraped-thingiverse'
    if (source.includes('ravelry')) return 'scraped-ravelry'
    if (source.includes('github')) return 'scraped-github'
    
    return 'user-submitted'
  }
}
```

---

## Error Handling

### Error Types

```typescript
// ✅ GOOD: Custom error classes
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class ValidationError extends Error {
  constructor(
    message: string,
    public field?: string
  ) {
    super(message)
    this.name = 'ValidationError'
  }
}
```

### Try-Catch Best Practices

```typescript
// ✅ GOOD: Specific error handling
try {
  const result = await processData()
  return result
} catch (error) {
  if (error instanceof ValidationError) {
    toast.error(`Validation failed: ${error.message}`)
    return null
  }
  
  if (error instanceof APIError && error.status === 404) {
    toast.error('Resource not found')
    return null
  }
  
  // Unexpected error - log and rethrow
  console.error('Unexpected error in processData:', error)
  throw error
}

// ❌ BAD: Silent error swallowing
try {
  await processData()
} catch (error) {
  // Do nothing
}

// ❌ BAD: Generic catch without logging
try {
  await processData()
} catch (error) {
  return null
}
```

### User-Facing Error Messages

```typescript
// ✅ GOOD: User-friendly messages
function getErrorMessage(error: unknown): string {
  if (error instanceof APIError) {
    switch (error.status) {
      case 400:
        return 'Invalid request. Please check your input.'
      case 401:
        return 'Please sign in to continue.'
      case 403:
        return 'You don\'t have permission to perform this action.'
      case 404:
        return 'The requested resource was not found.'
      case 500:
        return 'Server error. Please try again later.'
      default:
        return error.message || 'Something went wrong.'
    }
  }
  
  if (error instanceof Error) {
    return error.message
  }
  
  return 'An unexpected error occurred.'
}

// Usage
catch (error) {
  toast.error(getErrorMessage(error))
}
```

---

## Testing Standards

### Test Structure

```typescript
// ✅ GOOD: Descriptive test organization
describe('ProductCard', () => {
  describe('rendering', () => {
    it('displays product name', () => {
      const product = createMockProduct({ name: 'Test Product' })
      render(<ProductCard product={product} />)
      
      expect(screen.getByText('Test Product')).toBeInTheDocument()
    })
    
    it('shows product image when imageUrl is provided', () => {
      const product = createMockProduct({ 
        imageUrl: 'data:image/png;base64,abc123',
        imageAlt: 'Product image'
      })
      render(<ProductCard product={product} />)
      
      const image = screen.getByAltText('Product image')
      expect(image).toBeInTheDocument()
    })
  })
  
  describe('interactions', () => {
    it('calls onSelect when clicked', async () => {
      const handleSelect = vi.fn()
      const product = createMockProduct()
      render(<ProductCard product={product} onSelect={handleSelect} />)
      
      await userEvent.click(screen.getByRole('button'))
      
      expect(handleSelect).toHaveBeenCalledWith(product)
    })
  })
  
  describe('edge cases', () => {
    it('handles missing optional fields gracefully', () => {
      const product = createMockProduct({ 
        imageUrl: undefined,
        description: undefined
      })
      render(<ProductCard product={product} />)
      
      expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })
  })
})
```

### Test Helpers

```typescript
// ✅ GOOD: Reusable test utilities
export function createMockProduct(overrides?: Partial<Product>): Product {
  return {
    id: 'test-id',
    name: 'Test Product',
    type: 'Software',
    source: 'User',
    description: 'Test description',
    tags: ['test'],
    createdAt: Date.now(),
    origin: 'user-submitted',
    ...overrides
  }
}

export function createMockUser(overrides?: Partial<UserAccount>): UserAccount {
  return {
    id: 'user-1',
    githubId: 'user-1',
    login: 'testuser',
    avatarUrl: 'https://example.com/avatar.png',
    role: 'user',
    joinedAt: Date.now(),
    lastActive: Date.now(),
    productsSubmitted: 0,
    reviewsWritten: 0,
    ratingsGiven: 0,
    discussionsParticipated: 0,
    ...overrides
  }
}
```

### Async Testing

```typescript
// ✅ GOOD: Proper async test handling
it('loads products on mount', async () => {
  const mockProducts = [createMockProduct()]
  vi.spyOn(APIService, 'getAllProducts').mockResolvedValue(mockProducts)
  
  render(<ProductList />)
  
  // Wait for loading to complete
  await waitFor(() => {
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
  })
  
  // Verify products are displayed
  expect(screen.getByText(mockProducts[0].name)).toBeInTheDocument()
})

// ✅ GOOD: Testing error states
it('displays error message when fetch fails', async () => {
  vi.spyOn(APIService, 'getAllProducts').mockRejectedValue(
    new Error('Network error')
  )
  
  render(<ProductList />)
  
  await waitFor(() => {
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument()
  })
})
```

---

## Accessibility

### Semantic HTML

```typescript
// ✅ GOOD: Semantic elements
<nav aria-label="Main navigation">
  <ul>
    <li><a href="/">Home</a></li>
    <li><a href="/products">Products</a></li>
  </ul>
</nav>

<main id="main-content">
  <h1>Product List</h1>
  <section aria-labelledby="filters-heading">
    <h2 id="filters-heading">Filters</h2>
    {/* filter controls */}
  </section>
</main>

// ❌ BAD: Non-semantic div soup
<div className="nav">
  <div className="nav-items">
    <div onClick={goHome}>Home</div>
    <div onClick={goProducts}>Products</div>
  </div>
</div>
```
---

## Documentation

See also: Code Commenting Guidelines in [AGENT_GUIDE.md](AGENT_GUIDE.md#code-commenting-guidelines) for expectations on when and how to comment code, including JSDoc/TSDoc usage for exported symbols.

### JSDoc Comments

```typescript
/**
 * Calculates the average rating for a product
 * 
 * @param ratings - Array of rating objects for the product
 * @returns Average rating (0-5) or 0 if no ratings exist
 * 
 * @example
 * const ratings = [
 *   { rating: 5, userId: '1', productId: 'abc' },
 *   { rating: 3, userId: '2', productId: 'abc' }
 * ]
 * const avg = calculateAverageRating(ratings) // 4.0
 */
function calculateAverageRating(ratings: Rating[]): number {
  if (ratings.length === 0) return 0
  const sum = ratings.reduce((acc, r) => acc + r.rating, 0)
  return sum / ratings.length
}

/**
 * Merges scraped products with existing database products
 * 
 * Performs the following operations:
 * 1. Identifies new products not in database
 * 2. Identifies existing products that need updates
 * 3. Merges tags from both sources
 * 4. Preserves user edits and banned products
 * 
 * @param scrapedProducts - Products found by scrapers
 * @param existingProducts - Current products in database
 * @returns Object with products to add and update
 * 
 * @throws {Error} If scraping data is malformed
 */
async function mergeScrapedProducts(
  scrapedProducts: ScrapedProduct[],
  existingProducts: Product[]
): Promise<{ toAdd: Product[]; toUpdate: Product[] }> {
  // Implementation
}
```

### Component Documentation

```typescript
/**
 * ProductCard - Displays a product summary in grid or list view
 * 
 * Features:
 * - Product image with alt text
 * - Star rating display
 * - Quick actions (edit, delete for authorized users)
 * - Click to view details
 * 
 * @example
 * <ProductCard
 *   product={product}
 *   ratings={ratings}
 *   onClick={() => navigate(`/product/${product.id}`)}
 *   isAdmin={true}
 *   onDelete={handleDelete}
 * />
 */
interface ProductCardProps {
  /** Product to display */
  product: Product
  
  /** All ratings for this product */
  ratings: Rating[]
  
  /** Callback when card is clicked */
  onClick: () => void
  
  /** Whether current user is an admin */
  isAdmin?: boolean
  
  /** Whether current user is a moderator */
  isModerator?: boolean
  
  /** Callback when delete button is clicked (admin only) */
  onDelete?: (productId: string) => void
  
  /** Current user data */
  user?: UserData | null
  
  /** Callback when rating is submitted */
  onRate?: (productId: string, rating: number) => void
}

export function ProductCard({
  product,
  ratings,
  onClick,
  isAdmin = false,
  isModerator = false,
  onDelete,
  user,
  onRate
}: ProductCardProps) {
  // Implementation
}
```

### README Sections

Every major feature should have documentation:

1. **Purpose**: What problem does it solve?
2. **Usage**: How to use it (with examples)
3. **API**: Function signatures and parameters
4. **Edge Cases**: Known limitations or special behavior
5. **Testing**: How to test the feature

---

## Code Review Checklist

Before submitting a PR, ensure:

- [ ] Functions have JSDoc comments
- [ ] Error handling is comprehensive
- [ ] Tests are included and passing
- [ ] No console.log statements (use proper logging)
- [ ] State updates use functional form
- [ ] Loading and error states are handled
- [ ] User-facing messages are clear and helpful
- [ ] Code follows naming conventions
- [ ] No duplicate logic (DRY principle)
- [ ] Components are under 300 lines (split if larger)
- [ ] Functions are under 50 lines (split if larger)

---

**Last Updated**: January 2025
