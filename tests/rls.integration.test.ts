// Integration suite for supabase/migrations/0002_rls.sql. Runs against a
// real Supabase project (no Docker, no local Postgres) via `npm run
// test:rls`; see tests/README.md for the environment variables it needs
// and the fixture strategy. Every test that mutates data cleans up after
// itself so the suite can be re-run against the same project indefinitely
// without drifting.
//
// Two client kinds are used throughout:
// - `titolare` / `operatore`: anon-key clients signed in as real users of
//   an ephemeral "business A", created fresh in beforeAll.
// - `admin`: a service-role client. It bypasses RLS, which is exactly why
//   it is used for cross-tenant fixtures the anon key cannot create (e.g.
//   seeding "business B"), and for destructive setup/teardown that no
//   policy grants to an authenticated user (deleting a movement, deleting
//   a profile, deleting an auth.users row).
//
// One caveat worth stating up front: `lots_view`, `lot_stock` and
// `product_stock` all filter by `auth_business_id()`, which resolves via
// `auth.uid()`. The service-role key carries no `sub` claim, so
// `auth.uid()` is null for `admin` too - `admin` querying those views
// always gets zero rows, by the same mechanism that blocks an
// unauthenticated caller. `admin` is only useful against the base tables
// (lots, movements, profiles, ...), which it can read and write freely.

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { Client as PgClient } from 'pg';
import { randomUUID } from 'node:crypto';

jest.setTimeout(30_000);

const url = process.env.EXPO_PUBLIC_SUPABASE_URL!;
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!;
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

if (!process.env.SUPABASE_DB_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    'SUPABASE_DB_URL is not set: skipping the security_barrier leaky-predicate ' +
      "test in 'tenant isolation cannot be bypassed' (see tests/README.md - " +
      'PostgREST cannot express that test, so it needs a raw Postgres connection).',
  );
}

function newClient(key: string): SupabaseClient {
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

async function signIn(email: string, password: string): Promise<SupabaseClient> {
  const client = newClient(anonKey);
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) throw new Error(`could not sign in as ${email}: ${error.message}`);
  return client;
}

async function currentUserId(client: SupabaseClient): Promise<string> {
  const { data, error } = await client.auth.getUser();
  if (error || !data.user) throw new Error(`no session on client: ${error?.message}`);
  return data.user.id;
}

async function ownBusinessId(client: SupabaseClient): Promise<string> {
  const uid = await currentUserId(client);
  const { data, error } = await client.from('profiles').select('business_id').eq('id', uid).single();
  if (error || !data) throw new Error(`could not resolve business_id: ${error?.message}`);
  return data.business_id as string;
}

// ---------------------------------------------------------------- fixtures
// businessA is the long-lived tenant used by most tests below; businessB
// exists purely to prove the boundary between tenants and is never signed
// into directly - all of its rows are created and read through `admin`.

let admin: SupabaseClient;
let titolare: SupabaseClient;
let operatore: SupabaseClient;
let responsabile: SupabaseClient;
let titolareId: string;
let operatoreId: string;
let responsabileId: string;
let businessAId: string;
let businessBId: string;
let businessBOwnerId: string;

let supplierAId: string;
let productAId: string;
let pricedLotId: string; // a lot with a real unit_price, used by the price-visibility tests
let emptyLotId: string; // a lot with no movements at all, used by the lot_stock zero-row test
let lotInBId: string; // a lot that belongs to business B only

const createdUserIds: string[] = [];
const createdBusinessIds: string[] = [];

async function createBusiness(name: string): Promise<string> {
  const { data, error } = await admin.from('businesses').insert({ name }).select('id').single();
  if (error || !data) throw new Error(`could not create business "${name}": ${error?.message}`);
  createdBusinessIds.push(data.id as string);
  return data.id as string;
}

async function createUser(
  businessId: string,
  role: 'titolare' | 'responsabile' | 'operatore',
  active = true,
): Promise<{ id: string; email: string; password: string }> {
  const email = `rls-${role}-${randomUUID()}@fiestisima-tests.invalid`;
  const password = `Test-${randomUUID()}`;
  const { data, error } = await admin.auth.admin.createUser({ email, password, email_confirm: true });
  if (error || !data.user) throw new Error(`could not create auth user ${email}: ${error?.message}`);
  const id = data.user.id;
  createdUserIds.push(id);
  const { error: profileError } = await admin
    .from('profiles')
    .insert({ id, business_id: businessId, full_name: `RLS test ${role}`, role, active });
  if (profileError) throw new Error(`could not create profile for ${email}: ${profileError.message}`);
  return { id, email, password };
}

// Best-effort teardown for a single throwaway user: tolerate rows that a
// test already removed itself (e.g. test 13 deletes the blocking lot and
// the profile before calling this).
async function deleteUser(id: string): Promise<void> {
  try {
    await admin.from('profiles').delete().eq('id', id);
  } catch {
    /* already gone */
  }
  try {
    await admin.auth.admin.deleteUser(id);
  } catch {
    /* already gone */
  }
}

beforeAll(async () => {
  admin = newClient(serviceKey);

  businessAId = await createBusiness('RLS test business A');
  businessBId = await createBusiness('RLS test business B');

  const titolareCreds = await createUser(businessAId, 'titolare');
  const operatoreCreds = await createUser(businessAId, 'operatore');
  const responsabileCreds = await createUser(businessAId, 'responsabile');
  const businessBOwner = await createUser(businessBId, 'titolare');
  businessBOwnerId = businessBOwner.id;

  titolare = await signIn(titolareCreds.email, titolareCreds.password);
  operatore = await signIn(operatoreCreds.email, operatoreCreds.password);
  responsabile = await signIn(responsabileCreds.email, responsabileCreds.password);
  titolareId = await currentUserId(titolare);
  operatoreId = await currentUserId(operatore);
  responsabileId = await currentUserId(responsabile);

  // Baseline catalog for business A.
  const { data: supplier, error: supplierError } = await admin
    .from('suppliers')
    .insert({ business_id: businessAId, name: 'Metro Pescara' })
    .select('id')
    .single();
  if (supplierError || !supplier) throw new Error(`fixture: supplier: ${supplierError?.message}`);
  supplierAId = supplier.id as string;

  const { data: product, error: productError } = await admin
    .from('products')
    .insert({ business_id: businessAId, name: 'Pomodori pelati 400 g', barcode: '8001234567890' })
    .select('id')
    .single();
  if (productError || !product) throw new Error(`fixture: product: ${productError?.message}`);
  productAId = product.id as string;

  const { data: lot, error: lotError } = await admin
    .from('lots')
    .insert({
      business_id: businessAId,
      product_id: productAId,
      supplier_id: supplierAId,
      lot_code: 'L2409A',
      expires_on: '2027-03-12',
      unit_price: 0.89,
      document_url: 'https://example.invalid/fattura-l2409a.pdf',
      created_by: titolareId,
    })
    .select('id')
    .single();
  if (lotError || !lot) throw new Error(`fixture: priced lot: ${lotError?.message}`);
  pricedLotId = lot.id as string;

  const { data: emptyLot, error: emptyLotError } = await admin
    .from('lots')
    .insert({
      business_id: businessAId,
      product_id: productAId,
      lot_code: 'L2409B-NOMOV',
      created_by: titolareId,
    })
    .select('id')
    .single();
  if (emptyLotError || !emptyLot) throw new Error(`fixture: empty lot: ${emptyLotError?.message}`);
  emptyLotId = emptyLot.id as string;

  // Business B's own product + lot, used to prove tenant isolation. Given
  // an exact expires_on so the leaky-view test can target it precisely.
  const { data: productB, error: productBError } = await admin
    .from('products')
    .insert({ business_id: businessBId, name: 'Business B product' })
    .select('id')
    .single();
  if (productBError || !productB) throw new Error(`fixture: product B: ${productBError?.message}`);

  const { data: lotB, error: lotBError } = await admin
    .from('lots')
    .insert({
      business_id: businessBId,
      product_id: productB.id,
      lot_code: 'B-ONLY',
      expires_on: '2027-01-01',
      unit_price: 12.5,
      created_by: businessBOwnerId,
    })
    .select('id')
    .single();
  if (lotBError || !lotB) throw new Error(`fixture: lot B: ${lotBError?.message}`);
  lotInBId = lotB.id as string;
});

afterAll(async () => {
  // A single "delete from businesses" cannot cascade past
  // lots.created_by/movements.created_by, both "on delete restrict"
  // against profiles: RESTRICT is checked immediately and cannot be
  // deferred, and the cascade from businesses to profiles fires before -
  // not after - the cascades from businesses to lots and to movements, so
  // the whole statement would abort with a foreign key violation while
  // still-referenced lots/movements rows exist. Deleting in explicit
  // dependency order - movements, then lots, then profiles, then
  // businesses - avoids that entirely, and checking each step's error
  // means a teardown regression fails this hook loudly instead of leaving
  // two businesses, a full catalogue and three auth users behind on every
  // run without a trace.
  if (createdBusinessIds.length > 0) {
    const movementsDel = await admin.from('movements').delete().in('business_id', createdBusinessIds);
    if (movementsDel.error) throw new Error(`teardown: movements: ${movementsDel.error.message}`);

    const lotsDel = await admin.from('lots').delete().in('business_id', createdBusinessIds);
    if (lotsDel.error) throw new Error(`teardown: lots: ${lotsDel.error.message}`);

    const profilesDel = await admin.from('profiles').delete().in('business_id', createdBusinessIds);
    if (profilesDel.error) throw new Error(`teardown: profiles: ${profilesDel.error.message}`);

    // Everything else business-scoped (suppliers, categories, products,
    // events, invitations) has no restrict pointing at it once lots and
    // movements are gone, so the businesses' own cascade handles the rest.
    const businessesDel = await admin.from('businesses').delete().in('id', createdBusinessIds);
    if (businessesDel.error) throw new Error(`teardown: businesses: ${businessesDel.error.message}`);
  }
  for (const id of createdUserIds) {
    await deleteUser(id);
  }
});

// ============================================================ price / lots_view

describe('the price never leaves the database for an operatore', () => {
  it('a titolare receives unit_price and document_url from lots_view', async () => {
    const { data, error } = await titolare
      .from('lots_view')
      .select('lot_code, unit_price, document_url')
      .eq('id', pricedLotId)
      .single();
    expect(error).toBeNull();
    expect(data?.unit_price).toBe(0.89);
    expect(data?.document_url).not.toBeNull();
  });

  it('an operatore receives null for both unit_price and document_url', async () => {
    const { data, error } = await operatore
      .from('lots_view')
      .select('lot_code, unit_price, document_url')
      .eq('id', pricedLotId)
      .single();
    expect(error).toBeNull();
    expect(data?.unit_price).toBeNull();
    expect(data?.document_url).toBeNull();
  });

  it('an operatore selecting from lots directly is denied outright', async () => {
    const { data, error } = await operatore.from('lots').select('*');
    expect(error).not.toBeNull();
    expect(error?.code).toBe('42501'); // insufficient_privilege on unit_price/document_url
    expect(data).toBeNull();
  });

  it('a titolare selecting from lots directly is denied outright too - reads go through the view for everyone', async () => {
    // Note this is specifically about "*" (which pulls in unit_price and
    // document_url, columns nobody has select on): lots_select does let a
    // titolare/operatore select individual non-price columns straight off
    // the table now (see "the permission matrix" below) - that policy has
    // to exist for lots_update and insert-then-read-it-back to work at
    // all, and it was never the mechanism protecting the price.
    const { data, error } = await titolare.from('lots').select('*');
    expect(error).not.toBeNull();
    expect(error?.code).toBe('42501');
    expect(data).toBeNull();
  });
});

// ============================================================ column privileges on lots

describe('created_by and business_id on lots cannot be rewritten after the fact', () => {
  it('a titolare can correct lot_code but cannot reassign created_by or business_id', async () => {
    const fixture = await admin
      .from('lots')
      .insert({
        business_id: businessAId,
        product_id: productAId,
        lot_code: `COLPRIV-${randomUUID()}`,
        created_by: titolareId,
      })
      .select('id')
      .single();
    expect(fixture.error).toBeNull();
    const lotId = fixture.data!.id as string;

    try {
      const newCode = `COLPRIV-CORRECTED-${randomUUID()}`;
      const lotCodeUpdate = await titolare.from('lots').update({ lot_code: newCode }).eq('id', lotId).select('lot_code').single();
      expect(lotCodeUpdate.error).toBeNull();
      expect(lotCodeUpdate.data?.lot_code).toBe(newCode);

      // lots_insert pins created_by to the caller, but lots_update's own
      // with check only re-tests business_id - column privileges are what
      // actually stop an existing lot's audit trail from being rewritten,
      // for every role, titolare included.
      const createdByUpdate = await titolare.from('lots').update({ created_by: operatoreId }).eq('id', lotId);
      expect(createdByUpdate.error).not.toBeNull();
      expect(createdByUpdate.error?.code).toBe('42501');

      const businessIdUpdate = await titolare.from('lots').update({ business_id: businessBId }).eq('id', lotId);
      expect(businessIdUpdate.error).not.toBeNull();
      expect(businessIdUpdate.error?.code).toBe('42501');
    } finally {
      await admin.from('lots').delete().eq('id', lotId);
    }
  });
});

// ============================================================ catalog administration

describe('an operatore does not administer the catalog', () => {
  it('can read products', async () => {
    const { data, error } = await operatore.from('products').select('id, name');
    expect(error).toBeNull();
    expect(data?.length).toBeGreaterThan(0);
  });

  it('cannot create a product', async () => {
    const businessId = await ownBusinessId(operatore);
    const { error } = await operatore.from('products').insert({ business_id: businessId, name: 'Contrabando' });
    expect(error).not.toBeNull();
    expect(error?.code).toBe('42501'); // insufficient_privilege - products_write's with check rejects the role
  });

  it('cannot invite users', async () => {
    const businessId = await ownBusinessId(operatore);
    const { error } = await operatore.from('invitations').insert({
      business_id: businessId,
      email: `nadie-${randomUUID()}@example.com`,
      full_name: 'Nadie',
      role: 'operatore',
    });
    expect(error).not.toBeNull();
    expect(error?.code).toBe('42501'); // insufficient_privilege - invitations_all's with check rejects the role
  });
});

// ============================================================ the permission matrix's untested corners

describe('the permission matrix: rights the earlier rounds left untested', () => {
  it('an operatore can insert a lot - goods-in is everyone\'s job on the floor', async () => {
    const { data, error } = await operatore
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `OP-LOT-${randomUUID()}`, created_by: operatoreId })
      .select('id')
      .single();
    expect(error).toBeNull();
    expect(data?.id).toBeDefined();
    await admin.from('lots').delete().eq('id', data!.id);
  });

  it('an operatore can insert a movement - this is the central positive right of the whole app, and until now every insert in this file was made by titolare or admin', async () => {
    const { data, error } = await operatore
      .from('movements')
      .insert({ business_id: businessAId, lot_id: pricedLotId, type: 'carico', quantity: 1, created_by: operatoreId })
      .select('id')
      .single();
    expect(error).toBeNull();
    expect(data?.id).toBeDefined();
    await admin.from('movements').delete().eq('id', data!.id);
  });

  it('an operatore cannot update a lot', async () => {
    const fixture = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `OP-UPD-${randomUUID()}`, created_by: titolareId })
      .select('id')
      .single();
    expect(fixture.error).toBeNull();
    const lotId = fixture.data!.id as string;

    try {
      // Same shape as the movement-immutability tests above: lots_update's
      // USING clause excludes the row for an operatore, so PostgREST
      // reports success on zero matched rows rather than an error. The
      // invariant is that the row does not change.
      const updateResult = await operatore.from('lots').update({ lot_code: 'should-not-apply' }).eq('id', lotId);
      expect(updateResult.error).toBeNull();

      const { data } = await admin.from('lots').select('lot_code').eq('id', lotId).single();
      expect(data?.lot_code).not.toBe('should-not-apply');
    } finally {
      await admin.from('lots').delete().eq('id', lotId);
    }
  });

  it('a responsabile can update a lot', async () => {
    const fixture = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `RESP-UPD-${randomUUID()}`, created_by: titolareId })
      .select('id')
      .single();
    expect(fixture.error).toBeNull();
    const lotId = fixture.data!.id as string;

    try {
      const newCode = `RESP-UPD-DONE-${randomUUID()}`;
      const { data, error } = await responsabile
        .from('lots')
        .update({ lot_code: newCode })
        .eq('id', lotId)
        .select('lot_code')
        .single();
      expect(error).toBeNull();
      expect(data?.lot_code).toBe(newCode);
    } finally {
      await admin.from('lots').delete().eq('id', lotId);
    }
  });

  describe('businesses_update is restricted to titolare', () => {
    it('a titolare can update their own business', async () => {
      const { data: before } = await admin.from('businesses').select('name').eq('id', businessAId).single();
      const newName = `RLS test business A ${randomUUID()}`;
      const { data, error } = await titolare
        .from('businesses')
        .update({ name: newName })
        .eq('id', businessAId)
        .select('name')
        .single();
      expect(error).toBeNull();
      expect(data?.name).toBe(newName);
      // Restore, so the business's name doesn't churn pointlessly on every run.
      await admin.from('businesses').update({ name: before!.name }).eq('id', businessAId);
    });

    it('a responsabile cannot update the business', async () => {
      const { data: before } = await admin.from('businesses').select('name').eq('id', businessAId).single();
      const updateResult = await responsabile.from('businesses').update({ name: 'should-not-apply' }).eq('id', businessAId);
      expect(updateResult.error).toBeNull(); // same silent-zero-rows shape as the write-denial cases above
      const { data: after } = await admin.from('businesses').select('name').eq('id', businessAId).single();
      expect(after?.name).toBe(before?.name);
    });

    it('an operatore cannot update the business', async () => {
      const { data: before } = await admin.from('businesses').select('name').eq('id', businessAId).single();
      const updateResult = await operatore.from('businesses').update({ name: 'should-not-apply' }).eq('id', businessAId);
      expect(updateResult.error).toBeNull();
      const { data: after } = await admin.from('businesses').select('name').eq('id', businessAId).single();
      expect(after?.name).toBe(before?.name);
    });
  });
});

// ============================================================ immutable traceability

describe('the movement record is immutable', () => {
  let immutableMovementId: string;
  let immutableMovementQuantity: number;

  beforeAll(async () => {
    const { data, error } = await titolare
      .from('movements')
      .insert({ business_id: businessAId, lot_id: pricedLotId, type: 'carico', quantity: 7, created_by: titolareId })
      .select('id, quantity')
      .single();
    if (error || !data) throw new Error(`fixture: immutable movement: ${error?.message}`);
    immutableMovementId = data.id as string;
    immutableMovementQuantity = data.quantity as number;
  });

  afterAll(async () => {
    await admin.from('movements').delete().eq('id', immutableMovementId);
  });

  // With RLS on and no update/delete policy on movements, the USING filter
  // excludes the row silently - authenticated still holds the table-level
  // UPDATE/DELETE privilege (nothing here revokes it), so there is no
  // 42501 either. PostgREST reports that as a plain success (204, error
  // null), because as far as it can tell zero rows matched the request.
  // Asserting `error).not.toBeNull()` here would fail against a *correct*
  // implementation and, per "if a test fails, fix the policy, not the
  // test", would be an open invitation to loosen movements - the one table
  // the whole legal record depends on. The actual invariant is that the
  // row is unchanged, which only a follow-up read (via admin, since the
  // point is to check the real column value regardless of what the
  // titolare client is allowed to see) can confirm.
  it('an update from titolare reports success but does not change the row', async () => {
    const updateResult = await titolare.from('movements').update({ quantity: 999 }).eq('id', immutableMovementId);
    expect(updateResult.error).toBeNull();

    const { data, error } = await admin.from('movements').select('quantity').eq('id', immutableMovementId).single();
    expect(error).toBeNull();
    expect(data?.quantity).toBe(immutableMovementQuantity);
  });

  it('a delete from titolare reports success but does not remove the row', async () => {
    const deleteResult = await titolare.from('movements').delete().eq('id', immutableMovementId);
    expect(deleteResult.error).toBeNull();

    const { data, error } = await admin.from('movements').select('id').eq('id', immutableMovementId).single();
    expect(error).toBeNull();
    expect(data?.id).toBe(immutableMovementId);
  });
});

// ============================================================ stock computation

describe('stock is computed, not stored', () => {
  it('product_stock returns one row shape per product', async () => {
    const { data, error } = await titolare.from('product_stock').select('product_id, stock');
    expect(error).toBeNull();
    expect(Array.isArray(data)).toBe(true);
  });

  it('lot_stock on a lot with no movements returns a row with stock 0, not no row', async () => {
    const { data, error } = await titolare.from('lot_stock').select('stock').eq('lot_id', emptyLotId).single();
    expect(error).toBeNull();
    expect(data?.stock).toBe(0);
  });

  it('product_stock only sums within one business - business B never appears in business A\'s rows', async () => {
    const { data, error } = await titolare.from('product_stock').select('product_id');
    expect(error).toBeNull();
    const productIds = (data ?? []).map((row) => row.product_id);
    // productAId's own presence is exercised by the reversal-signs test
    // below; the point here is that no business-B product id ever leaks in.
    expect(productIds).not.toContain(null);
    const { data: businessBProducts } = await admin.from('products').select('id').eq('business_id', businessBId);
    for (const row of businessBProducts ?? []) {
      expect(productIds).not.toContain(row.id);
    }
  });

  describe('the four reversal sign cases', () => {
    let reversalLotId: string;

    beforeAll(async () => {
      const { data, error } = await admin
        .from('lots')
        .insert({ business_id: businessAId, product_id: productAId, lot_code: `REV-${randomUUID()}`, created_by: titolareId })
        .select('id')
        .single();
      if (error || !data) throw new Error(`fixture: reversal lot: ${error?.message}`);
      reversalLotId = data.id as string;
    });

    afterAll(async () => {
      await admin.from('movements').delete().eq('lot_id', reversalLotId);
      await admin.from('lots').delete().eq('id', reversalLotId);
    });

    async function stockOf(lotId: string): Promise<number> {
      const { data, error } = await titolare.from('lot_stock').select('stock').eq('lot_id', lotId).single();
      if (error) throw new Error(`could not read lot_stock: ${error.message}`);
      return data!.stock as number;
    }

    async function insertMovement(overrides: Record<string, unknown>) {
      const { error } = await titolare.from('movements').insert({
        business_id: businessAId,
        lot_id: reversalLotId,
        type: 'carico',
        quantity: 1,
        created_by: titolareId,
        ...overrides,
      });
      if (error) throw new Error(`could not insert movement fixture: ${error.message}`);
    }

    it('a plain carico adds', async () => {
      await insertMovement({ type: 'carico', quantity: 10 });
      expect(await stockOf(reversalLotId)).toBe(10);
    });

    it('a reversal of a carico subtracts', async () => {
      const { data: firstCarico } = await admin
        .from('movements')
        .select('id')
        .eq('lot_id', reversalLotId)
        .eq('type', 'carico')
        .is('reverses_id', null)
        .single();
      await insertMovement({ type: 'carico', quantity: 10, reverses_id: firstCarico!.id });
      expect(await stockOf(reversalLotId)).toBe(0);
    });

    it('a plain scarico/scarto subtracts', async () => {
      await insertMovement({ type: 'scarico_vendita', quantity: 3 });
      expect(await stockOf(reversalLotId)).toBe(-3);
    });

    it('a reversal of a scarico adds back', async () => {
      const { data: theScarico } = await admin
        .from('movements')
        .select('id')
        .eq('lot_id', reversalLotId)
        .eq('type', 'scarico_vendita')
        .single();
      await insertMovement({ type: 'scarico_vendita', quantity: 3, reverses_id: theScarico!.id });
      expect(await stockOf(reversalLotId)).toBe(0);
    });
  });
});

// ============================================================ tenant isolation cannot be bypassed

describe('tenant isolation cannot be bypassed', () => {
  it('a movement cannot reference a lot from another business', async () => {
    const { error } = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: lotInBId,
      type: 'carico',
      quantity: 1,
      created_by: titolareId,
    });
    // The composite foreign key (lot_id, business_id) references
    // lots (id, business_id): lotInBId only pairs with businessBId there,
    // so pairing it with businessAId here matches no row and is rejected.
    expect(error).not.toBeNull();
    expect(error?.code).toBe('23503'); // foreign_key_violation
  });

  it('a leaky, caller-supplied predicate against lots_view does not surface business B\'s row', async () => {
    // A plain value filter for a lot_code that only exists in business B:
    // if the tenant boundary were anything other than absolute, this would
    // return that row. It must come back empty, not merely with the price
    // hidden.
    const { data, error } = await operatore.from('lots_view').select('id').eq('lot_code', 'B-ONLY');
    expect(error).toBeNull();
    expect(data).toEqual([]);
  });

  // This one needs a direct Postgres connection (SUPABASE_DB_URL), not just
  // the anon/service-role keys the rest of the suite runs on - see the
  // comment inside the test for why, and tests/README.md for why that
  // credential is kept optional. Skip cleanly and say so by name rather
  // than making the whole suite depend on a credential far more sensitive
  // than what every other test needs.
  const itWithDbUrl = process.env.SUPABASE_DB_URL ? it : it.skip;

  itWithDbUrl('a predicate that only errors on business B\'s underlying row does not leak its existence via that error (requires SUPABASE_DB_URL)', async () => {
    // This is the textbook security_barrier proof (see the Postgres manual's
    // own CREATE VIEW ... WITH (security_barrier) example): business B's
    // fixture lot has expires_on = 2027-01-01 and no business-A lot shares
    // that date, so "1 / (expires_on - date '2027-01-01')" divides by zero
    // only for that one row. Without security_barrier the planner is free
    // to evaluate this WHERE clause before the view's own
    // "business_id = auth_business_id()" filter, and the division error
    // would surface even though the row should never reach this
    // operatore's session. This needs a raw connection: PostgREST's filter
    // grammar only accepts fixed operators against literals, so it cannot
    // express a caller-supplied expression like this at all - which is
    // itself part of why this class of leak is hard to exploit through the
    // REST API, but the view still has to hold up against a client that
    // does have SQL access (e.g. a future reporting tool built directly on
    // the database).
    const pg = new PgClient({ connectionString: process.env.SUPABASE_DB_URL });
    await pg.connect();
    try {
      await pg.query('begin');
      await pg.query('set local role authenticated');
      await pg.query('select set_config($1, $2, true)', [
        'request.jwt.claims',
        JSON.stringify({ sub: operatoreId, role: 'authenticated' }),
      ]);
      // If security_barrier is doing its job, business B's row is excluded
      // by the view's own tenant filter before this division ever runs
      // against it, so the query below resolves cleanly. Without it,
      // Postgres is free to evaluate the caller's WHERE clause first and
      // this throws "division by zero" instead, which fails this test - a
      // rejected promise here is itself the regression signal, on top of
      // the row-level assertion below.
      const result = await pg.query(
        "select id from lots_view where 1 / (expires_on - date '2027-01-01') > 0",
      );
      expect(result.rows.some((row) => row.id === lotInBId)).toBe(false);
    } finally {
      await pg.query('rollback').catch(() => undefined);
      await pg.end();
    }
  });
});

// ============================================================ unauthenticated / deactivated callers

describe('auth_business_id() and auth_role() are null with no active session', () => {
  it('are null for a caller with no session at all, and the three views deny outright rather than returning zero rows', async () => {
    const anon = newClient(anonKey);
    const { data: businessIdData, error: businessIdError } = await anon.rpc('auth_business_id');
    expect(businessIdError).toBeNull();
    expect(businessIdData).toBeNull();

    const { data: roleData, error: roleError } = await anon.rpc('auth_role');
    expect(roleError).toBeNull();
    expect(roleData).toBeNull();

    // anon has no select grant on these views at all (0002 revokes it
    // explicitly): a caller with no session gets a permission error, not
    // an empty result. Zero rows would say "you asked correctly and there
    // is nothing here"; a permission error says "you are not allowed to
    // ask", which is the true statement for a caller with no session, and
    // the one that fails loudly if a screen ever queries before signing in.
    for (const view of ['lots_view', 'lot_stock', 'product_stock'] as const) {
      const { data, error } = await anon.from(view).select('*');
      expect(error).not.toBeNull();
      expect(error?.code).toBe('42501'); // insufficient_privilege
      expect(data).toBeNull();
    }
  });

  it('are null for a deactivated profile, and the three views return zero rows', async () => {
    const throwaway = await createUser(businessAId, 'operatore');
    const client = await signIn(throwaway.email, throwaway.password);
    try {
      // Sanity check: while active, the function resolves normally.
      const { data: activeBusinessId } = await client.rpc('auth_business_id');
      expect(activeBusinessId).toBe(businessAId);

      await admin.from('profiles').update({ active: false }).eq('id', throwaway.id);

      const { data: businessIdData, error: businessIdError } = await client.rpc('auth_business_id');
      expect(businessIdError).toBeNull();
      expect(businessIdData).toBeNull();

      const { data: roleData, error: roleError } = await client.rpc('auth_role');
      expect(roleError).toBeNull();
      expect(roleData).toBeNull();

      // Unlike the anonymous case above, this caller *is* authenticated and
      // still has select on the three views - auth_business_id() is null
      // only because of the "and active" filter inside it, so the views'
      // own tenant filter correctly excludes every row. Zero rows is the
      // right answer here, not a permission error.
      for (const view of ['lots_view', 'lot_stock', 'product_stock'] as const) {
        const { data, error } = await client.from(view).select('*');
        expect(error).toBeNull();
        expect(data).toEqual([]);
      }
    } finally {
      await deleteUser(throwaway.id);
    }
  });
});

// ============================================================ role/active changes are gated by the caller

describe('profiles_block_self_role_change_trg gates role/active changes by the caller\'s role, not by whose row it is', () => {
  it('an operatore cannot set their own role to titolare', async () => {
    const throwaway = await createUser(businessAId, 'operatore');
    const client = await signIn(throwaway.email, throwaway.password);
    try {
      const { error } = await client.from('profiles').update({ role: 'titolare' }).eq('id', throwaway.id);
      expect(error).not.toBeNull();
      // The trigger raises with an explicit errcode so this is
      // distinguishable from a generic PL/pgSQL exception (P0001) or from
      // an RLS policy violation, both of which are also plausible-sounding
      // failures on this same call.
      expect(error?.code).toBe('42501');

      const { data: afterAttempt } = await admin.from('profiles').select('role').eq('id', throwaway.id).single();
      expect(afterAttempt?.role).toBe('operatore');
    } finally {
      await deleteUser(throwaway.id);
    }
  });

  it('a titolare can change a responsabile to operatore, including via the colleague-update policy', async () => {
    const throwaway = await createUser(businessAId, 'responsabile');
    try {
      const { error } = await titolare.from('profiles').update({ role: 'operatore' }).eq('id', throwaway.id);
      expect(error).toBeNull();

      const { data: afterChange } = await admin.from('profiles').select('role').eq('id', throwaway.id).single();
      expect(afterChange?.role).toBe('operatore');
    } finally {
      await deleteUser(throwaway.id);
    }
  });
});

// ============================================================ movement validation

describe('movement validation constraints', () => {
  it('two inserts with the same client_id produce one movement; the second is a recognisable conflict', async () => {
    const clientId = randomUUID();
    const first = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: pricedLotId,
      type: 'carico',
      quantity: 1,
      created_by: titolareId,
      client_id: clientId,
    });
    expect(first.error).toBeNull();

    const second = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: pricedLotId,
      type: 'carico',
      quantity: 1,
      created_by: titolareId,
      client_id: clientId,
    });
    expect(second.error).not.toBeNull();
    // 23505 = unique_violation. The offline queue can treat this
    // specifically as "already synced", rather than as a generic failure.
    expect(second.error?.code).toBe('23505');

    const { count } = await admin
      .from('movements')
      .select('id', { count: 'exact', head: true })
      .eq('client_id', clientId);
    expect(count).toBe(1);

    await admin.from('movements').delete().eq('client_id', clientId);
  });

  it('rejects a scarto with a null reason', async () => {
    const { error } = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: pricedLotId,
      type: 'scarto',
      quantity: 1,
      reason: null,
      created_by: titolareId,
    });
    expect(error).not.toBeNull();
    expect(error?.code).toBe('23514'); // check_violation: scarto_needs_reason
  });

  it('rejects quantity = 0', async () => {
    const { error } = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: pricedLotId,
      type: 'carico',
      quantity: 0,
      created_by: titolareId,
    });
    expect(error).not.toBeNull();
    expect(error?.code).toBe('23514');
  });

  it('rejects quantity < 0', async () => {
    const { error } = await titolare.from('movements').insert({
      business_id: businessAId,
      lot_id: pricedLotId,
      type: 'carico',
      quantity: -1,
      created_by: titolareId,
    });
    expect(error).not.toBeNull();
    expect(error?.code).toBe('23514');
  });
});

// ============================================================ lot / product uniqueness

describe('lot and product uniqueness constraints', () => {
  it('two identical carico entries with null expires_on and null supplier_id collide', async () => {
    const lotCode = `NULLTEST-${randomUUID()}`;
    const first = await titolare.from('lots').insert({
      business_id: businessAId,
      product_id: productAId,
      lot_code: lotCode,
      created_by: titolareId,
    });
    expect(first.error).toBeNull();

    const second = await titolare.from('lots').insert({
      business_id: businessAId,
      product_id: productAId,
      lot_code: lotCode,
      created_by: titolareId,
    });
    expect(second.error).not.toBeNull();
    expect(second.error?.code).toBe('23505');

    await admin.from('lots').delete().eq('business_id', businessAId).eq('lot_code', lotCode);
  });

  it('two products in the same business with a null barcode both insert', async () => {
    const first = await titolare
      .from('products')
      .insert({ business_id: businessAId, name: `No barcode A ${randomUUID()}` })
      .select('id')
      .single();
    expect(first.error).toBeNull();

    const second = await titolare
      .from('products')
      .insert({ business_id: businessAId, name: `No barcode B ${randomUUID()}` })
      .select('id')
      .single();
    expect(second.error).toBeNull();

    await admin.from('products').delete().in('id', [first.data!.id, second.data!.id]);
  });
});

// ============================================================ delete actions on foreign keys

describe('delete actions on foreign keys', () => {
  it('deleting a profile sets invitations.invited_by and products.updated_by to null, and leaves business_id untouched', async () => {
    const thrower = await createUser(businessAId, 'operatore');
    let invitationId: string | undefined;
    let taggedProductId: string | undefined;
    try {
      const invitation = await admin
        .from('invitations')
        .insert({
          business_id: businessAId,
          email: `fk-test-${randomUUID()}@example.com`,
          full_name: 'FK test invite',
          invited_by: thrower.id,
        })
        .select('id')
        .single();
      expect(invitation.error).toBeNull();
      invitationId = invitation.data!.id as string;

      const taggedProduct = await admin
        .from('products')
        .insert({ business_id: businessAId, name: `FK test product ${randomUUID()}`, updated_by: thrower.id })
        .select('id')
        .single();
      expect(taggedProduct.error).toBeNull();
      taggedProductId = taggedProduct.data!.id as string;

      // A real delete, not an update: this is the only way to prove the
      // "on delete set null (col)" clause actually names the child column
      // and not the whole composite key (which would also null business_id
      // and fail its not-null constraint - the exact bug the previous
      // review round fixed).
      const del = await admin.from('profiles').delete().eq('id', thrower.id);
      expect(del.error).toBeNull();

      const { data: invitationAfter } = await admin
        .from('invitations')
        .select('invited_by, business_id')
        .eq('id', invitationId)
        .single();
      expect(invitationAfter?.invited_by).toBeNull();
      expect(invitationAfter?.business_id).toBe(businessAId);

      const { data: productAfter } = await admin
        .from('products')
        .select('updated_by, business_id')
        .eq('id', taggedProductId)
        .single();
      expect(productAfter?.updated_by).toBeNull();
      expect(productAfter?.business_id).toBe(businessAId);
    } finally {
      if (invitationId) await admin.from('invitations').delete().eq('id', invitationId);
      if (taggedProductId) await admin.from('products').delete().eq('id', taggedProductId);
      await deleteUser(thrower.id);
    }
  });

  it('deleting a category sets products.category_id to null, and leaves business_id untouched', async () => {
    const category = await admin
      .from('categories')
      .insert({ business_id: businessAId, name: `FK test category ${randomUUID()}` })
      .select('id')
      .single();
    expect(category.error).toBeNull();

    const product = await admin
      .from('products')
      .insert({ business_id: businessAId, name: `Categorised product ${randomUUID()}`, category_id: category.data!.id })
      .select('id')
      .single();
    expect(product.error).toBeNull();

    const del = await admin.from('categories').delete().eq('id', category.data!.id);
    expect(del.error).toBeNull();

    const { data: productAfter } = await admin
      .from('products')
      .select('category_id, business_id')
      .eq('id', product.data!.id)
      .single();
    expect(productAfter?.category_id).toBeNull();
    expect(productAfter?.business_id).toBe(businessAId);

    await admin.from('products').delete().eq('id', product.data!.id);
  });

  it('deleting a reversed movement sets the reversing movement\'s reverses_id to null, and leaves business_id untouched', async () => {
    const lot = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `FK-REV-${randomUUID()}`, created_by: titolareId })
      .select('id')
      .single();
    expect(lot.error).toBeNull();
    const lotId = lot.data!.id as string;

    const original = await admin
      .from('movements')
      .insert({ business_id: businessAId, lot_id: lotId, type: 'carico', quantity: 5, created_by: titolareId })
      .select('id')
      .single();
    expect(original.error).toBeNull();

    const reversal = await admin
      .from('movements')
      .insert({
        business_id: businessAId,
        lot_id: lotId,
        type: 'carico',
        quantity: 5,
        reverses_id: original.data!.id,
        created_by: titolareId,
      })
      .select('id')
      .single();
    expect(reversal.error).toBeNull();

    const del = await admin.from('movements').delete().eq('id', original.data!.id);
    expect(del.error).toBeNull();

    const { data: reversalAfter } = await admin
      .from('movements')
      .select('reverses_id, business_id')
      .eq('id', reversal.data!.id)
      .single();
    expect(reversalAfter?.reverses_id).toBeNull();
    expect(reversalAfter?.business_id).toBe(businessAId);

    await admin.from('movements').delete().eq('id', reversal.data!.id);
    await admin.from('lots').delete().eq('id', lotId);
  });

  it('deleting an event that has movements against it errors instead of orphaning them', async () => {
    const event = await admin
      .from('events')
      .insert({ business_id: businessAId, name: `FK test event ${randomUUID()}`, event_date: '2026-12-31' })
      .select('id')
      .single();
    expect(event.error).toBeNull();
    const eventId = event.data!.id as string;

    const lot = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `FK-EVT-${randomUUID()}`, created_by: titolareId })
      .select('id')
      .single();
    const lotId = lot.data!.id as string;

    const movement = await admin
      .from('movements')
      .insert({
        business_id: businessAId,
        lot_id: lotId,
        event_id: eventId,
        type: 'scarico_vendita',
        quantity: 1,
        created_by: titolareId,
      })
      .select('id')
      .single();
    expect(movement.error).toBeNull();

    const del = await admin.from('events').delete().eq('id', eventId);
    expect(del.error).not.toBeNull();
    expect(del.error?.code).toBe('23503'); // foreign_key_violation

    await admin.from('movements').delete().eq('id', movement.data!.id);
    await admin.from('lots').delete().eq('id', lotId);
    await admin.from('events').delete().eq('id', eventId);
  });

  it('deleting the auth.users row for a user who created a lot fails; deactivating them is the supported path', async () => {
    const thrower = await createUser(businessAId, 'operatore');
    const lot = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: `FK-USER-${randomUUID()}`, created_by: thrower.id })
      .select('id')
      .single();
    expect(lot.error).toBeNull();
    const lotId = lot.data!.id as string;

    // auth.users -> profiles is "on delete cascade"; profiles -> lots is
    // "on delete restrict" via created_by. Deleting the user cascades
    // toward deleting their profile, which the still-existing lot blocks -
    // the whole delete fails, it does not silently orphan the lot.
    const { error: deleteUserError } = await admin.auth.admin.deleteUser(thrower.id);
    expect(deleteUserError).not.toBeNull();

    const { error: deactivateError } = await admin.from('profiles').update({ active: false }).eq('id', thrower.id);
    expect(deactivateError).toBeNull();

    const client = await signIn(thrower.email, thrower.password);
    const { data: businessIdData } = await client.rpc('auth_business_id');
    expect(businessIdData).toBeNull();
    const { data: roleData } = await client.rpc('auth_role');
    expect(roleData).toBeNull();

    await admin.from('lots').delete().eq('id', lotId);
    await deleteUser(thrower.id);
  });
});

// ============================================================ timestamps

describe('timestamps', () => {
  it('received_on stores the Rome calendar date for the instant of insert, not the UTC one', async () => {
    const lotCode = `TZ-${randomUUID()}`;
    const { data, error } = await admin
      .from('lots')
      .insert({ business_id: businessAId, product_id: productAId, lot_code: lotCode, created_by: titolareId })
      .select('received_on, created_at')
      .single();
    expect(error).toBeNull();

    // created_at and received_on share the same default, "now()", which is
    // stable within one statement - so created_at (a timestamptz, hence
    // unambiguous) tells us exactly what instant received_on's default was
    // computed against. This is what proves the Rome-vs-UTC distinction on
    // any day the test happens to run, including the roughly one-hour
    // (CET) or two-hour (CEST) window after UTC midnight where the two
    // calendar dates actually differ.
    const insertedAt = new Date(data!.created_at as string);
    const expectedRomeDate = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome' }).format(insertedAt);
    expect(data!.received_on).toBe(expectedRomeDate);

    await admin.from('lots').delete().eq('business_id', businessAId).eq('lot_code', lotCode);
  });

  it('an explicitly backdated occurred_at is preserved while created_at takes insert time', async () => {
    const occurredAt = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(); // 30 days ago
    const beforeInsert = Date.now();
    const { data, error } = await titolare
      .from('movements')
      .insert({
        business_id: businessAId,
        lot_id: pricedLotId,
        type: 'carico',
        quantity: 1,
        created_by: titolareId,
        occurred_at: occurredAt,
      })
      .select('id, occurred_at, created_at')
      .single();
    expect(error).toBeNull();
    expect(new Date(data!.occurred_at as string).getTime()).toBe(new Date(occurredAt).getTime());
    const createdAtMs = new Date(data!.created_at as string).getTime();
    expect(createdAtMs).toBeGreaterThanOrEqual(beforeInsert);
    expect(createdAtMs).toBeLessThan(beforeInsert + 30_000);

    await admin.from('movements').delete().eq('id', data!.id);
  });
});
