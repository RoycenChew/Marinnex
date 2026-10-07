import { Highlight, themes } from 'prism-react-renderer'
import { useTheme } from '../lib/theme'

/**
 * Syntax-highlighted code.
 *
 * The theme follows the app's, because a light code block on a dark page is the
 * brightest thing on screen and pulls the eye away from whatever the page is
 * actually about.
 */
export function CodeBlock({
  code,
  language,
  className,
}: {
  code: string
  language: string
  className?: string
}) {
  const { resolved } = useTheme()
  return (
    <Highlight
      code={code.trim()}
      language={language}
      theme={resolved === 'dark' ? themes.vsDark : themes.github}
    >
      {({ style, tokens, getLineProps, getTokenProps }) => (
        <pre
          className={
            'overflow-x-auto p-4 text-xs leading-relaxed ' + (className ?? '')
          }
          style={{ ...style, background: 'transparent', fontFamily: 'var(--font-mono)' }}
        >
          {tokens.map((line, i) => {
            const lineProps = getLineProps({ line })
            return (
              <div key={i} {...lineProps}>
                {line.map((token, key) => {
                  const tokenProps = getTokenProps({ token })
                  return <span key={key} {...tokenProps} />
                })}
              </div>
            )
          })}
        </pre>
      )}
    </Highlight>
  )
}
