export const t = {
  common: {
    save: 'Salva',
    cancel: 'Annulla',
    edit: 'Modifica',
    retry: 'Riprova',
    search: 'Cerca',
    clearSearch: 'Cancella la ricerca',
    close: 'Chiudi',
    days: 'giorni',
    daysAgo: 'gg fa',
    loading: 'Caricamento…',
  },
  auth: {
    signInTitle: 'Accedi',
    subtitle: 'Gestione del magazzino e degli eventi del locale.',
    email: 'Email',
    password: 'Password',
    showPassword: 'Mostra',
    hidePassword: 'Nascondi',
    submit: 'Entra',
    forgot: 'Password dimenticata?',
    forgotNeedsEmail: 'Scrivi prima la tua email, poi tocca di nuovo.',
    forgotSent: 'Se esiste un account con questa email, ti arriveranno le istruzioni per cambiare la password.',
    invalidCredentials: 'Email o password non corretti.',
    tooManyAttempts: 'Troppi tentativi. Riprova tra 15 minuti.',
    deactivated: 'Il tuo account è stato disattivato. Contatta il titolare.',
    invitationExpired: 'Questo invito è scaduto. Chiedine uno nuovo al titolare.',
    emailTaken: 'Questa email ha già un account. Accedi invece di registrarti.',
    invalidToken: 'Il link non è valido o è scaduto.',
    offline: 'Nessuna connessione. Riprova quando torni online.',
  },
  nav: {
    oggi: 'Oggi',
    prodotti: 'Prodotti',
    scadenze: 'Scadenze',
    scansiona: 'Scansiona',
    altro: 'Altro',
    registro: 'Registro',
    fornitori: 'Fornitori',
    utenti: 'Utenti',
    impostazioni: 'Impostazioni',
    signOut: 'Esci',
    comingSoonTitle: 'Presto disponibile',
    comingSoon: 'Arriva con il Blocco A.',
  },
  resetPassword: {
    title: 'Nuova password',
    subtitle: 'Scegli una password nuova per il tuo account.',
    newPassword: 'Nuova password',
    repeat: 'Ripeti',
    submit: 'Salva la password',
    tooShort: 'La password deve avere almeno 8 caratteri.',
    mismatch: 'Le due password non coincidono.',
    done: 'Password aggiornata. Ora puoi accedere.',
    backToSignIn: 'Vai ad Accedi',
  },
  invite: {
    title: 'Completa la registrazione',
    fullName: 'Nome e cognome',
    choosePassword: 'Scegli una password',
    submit: 'Entra in Fiestisima',
    expired: 'Questo invito è scaduto. Chiedine uno nuovo al titolare.',
  },
  products: {
    title: 'Prodotti',
    emptyTitle: 'Nessun prodotto',
    emptyAction: 'Aggiungi il primo',
    noResultsTitle: 'Nessun risultato',
    noResultsMessage: (query: string) => `Nessun prodotto per "${query}".`,
    add: 'Nuovo prodotto',
    name: 'Nome',
    barcode: 'Codice a barre',
    brand: 'Marca',
    unit: 'Unità',
    storage: 'Conservazione',
    minStock: 'Scorta minima',
    hasExpiry: 'Ha una scadenza',
    inStock: 'in magazzino',
    activeLots: 'lotti attivi',
    duplicateBarcode: (name: string) => `Questo codice è già associato a "${name}".`,
    barcodeLocked: 'Il codice a barre non si può cambiare: il prodotto ha già dei lotti.',
  },
  oggi: {
    greeting: (business: string) => `Ciao! Ecco lo stato di ${business}.`,
    productsInCatalog: 'Prodotti a catalogo',
    expiringSoon: 'In scadenza',
    lowStock: 'Sotto scorta',
    comingSoonCaption: 'Arriva col Blocco A',
    quickActions: 'Azioni rapide',
    searchProducts: 'Cerca un prodotto',
  },
  errors: {
    generic: 'Qualcosa non ha funzionato. Riprova.',
    onlyTitolare: 'Solo il titolare può gestire gli utenti.',
    // A write the user attempted came back 403 or 404 — per the API contract
    // (ruling v2-15) RLS-filtered writes can answer either way, and the UI
    // never distinguishes "forbidden" from "not found" for an action it
    // already tried to hide.
    notPermitted: 'Non hai il permesso per questa azione.',
  },
} as const;

const ROLE_LABELS: Record<string, string> = {
  titolare: 'Titolare',
  responsabile: 'Responsabile',
  operatore: 'Operatore',
};

/**
 * `ProfileOut.role` travels as a plain string, not a literal union (the API
 * is the source of truth for which roles exist). Falls back to the raw
 * value for one this client does not recognise, rather than hiding it.
 */
export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}
