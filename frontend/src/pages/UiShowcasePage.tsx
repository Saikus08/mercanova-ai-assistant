import { useState, type ReactNode } from 'react'
import {
  Badge,
  Button,
  Card,
  Input,
  Modal,
  Spinner,
  type BadgeVariant,
  type ButtonVariant,
} from '../components/ui'
import styles from './UiShowcasePage.module.css'

const BUTTON_VARIANTS: ButtonVariant[] = ['primary', 'secondary', 'ghost', 'danger']
const BADGE_VARIANTS: Array<{ variant: BadgeVariant; label: string }> = [
  { variant: 'neutral', label: 'Nuevo' },
  { variant: 'success', label: 'En stock' },
  { variant: 'warning', label: 'Últimas unidades' },
  { variant: 'danger', label: 'Sin stock' },
]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      {children}
    </section>
  )
}

/** "Storybook-lite": every UI atom and variant on one page, for review. */
export function UiShowcasePage() {
  const [isModalOpen, setModalOpen] = useState(false)

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Componentes de interfaz</h1>
        <p className={styles.muted}>
          Todos los componentes base y sus variantes. Los colores y medidas salen de los tokens
          de diseño.
        </p>
      </header>

      <Section title="Button">
        {(['md', 'sm'] as const).map((size) => (
          <div key={size} className={styles.row}>
            {BUTTON_VARIANTS.map((variant) => (
              <Button key={variant} variant={variant} size={size}>
                {variant} {size}
              </Button>
            ))}
          </div>
        ))}
        <div className={styles.row}>
          <Button disabled>Deshabilitado</Button>
          <Button variant="secondary" disabled>
            Deshabilitado
          </Button>
          <Button loading>Guardando</Button>
          <Button variant="secondary" loading>
            Cargando
          </Button>
        </div>
      </Section>

      <Section title="Badge">
        <div className={styles.row}>
          {BADGE_VARIANTS.map(({ variant, label }) => (
            <Badge key={variant} variant={variant}>
              {label}
            </Badge>
          ))}
        </div>
      </Section>

      <Section title="Input">
        <div className={styles.grid}>
          <Input label="Nombre" placeholder="Ana Pérez" />
          <Input label="Email" type="email" required hint="Te enviamos el comprobante acá." />
          <Input
            label="Dirección"
            defaultValue="Av. 18"
            error="La dirección debe incluir número de puerta."
          />
          <Input label="Depósito" defaultValue="MercaNova Centro" disabled />
        </div>
      </Section>

      <Section title="Card">
        <div className={styles.grid}>
          <Card>
            <p>Tarjeta con espaciado mediano (por defecto).</p>
          </Card>
          <Card padding="lg">
            <p>Tarjeta con espaciado grande.</p>
          </Card>
          <Card padding="none">
            <p className={styles.flush}>Tarjeta sin espaciado interno.</p>
          </Card>
        </div>
      </Section>

      <Section title="Spinner">
        <div className={styles.row}>
          <Spinner size="sm" />
          <Spinner size="md" />
          <Spinner size="lg" />
        </div>
      </Section>

      <Section title="Modal">
        <div className={styles.row}>
          <Button onClick={() => setModalOpen(true)}>Abrir modal</Button>
        </div>
        <Modal
          open={isModalOpen}
          title="Confirmar compra"
          onClose={() => setModalOpen(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setModalOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={() => setModalOpen(false)}>Confirmar compra</Button>
            </>
          }
        >
          <p>Ejemplo de ventana de confirmación. Se cierra con Escape o con el botón de cerrar.</p>
        </Modal>
      </Section>
    </div>
  )
}
