import { describe, expect, it } from 'vitest'

import { withoutTitle } from './analytics'

describe('withoutTitle', () => {
  it('sends every page under the site’s name, whatever its title holds', () => {
    const payload = { website: 'id', url: '/employees/10', title: 'Ana Rivera · Northwind Sales' }
    expect(withoutTitle('event', payload)).toEqual({ website: 'id', url: '/employees/10', title: 'Northwind Sales' })
  })
})
