import { guard } from './guard'

export const collect = <Node>(schema: object, key: string): Node[] => {
  const result: Node[] = []

  const walk = (node: unknown) => {
    if (!guard.obj(node)) return

    if (key in node) {
      const arr = Array.isArray(node[key])
      const nodes = arr ? (node[key] as Node[]) : [node[key] as Node]

      result.push(...nodes)
    }

    Object.values(node).forEach(walk)
  }

  walk(schema)

  return result
}
