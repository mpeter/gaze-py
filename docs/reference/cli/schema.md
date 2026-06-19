# gazepy schema

Emit the JSON schema for `AnalysisResult` output.

## Synopsis

```
gazepy schema
```

## Description

Prints the JSON schema that describes the structure of `gazepy analyze` and `gazepy crap` JSON output. Use this to validate output programmatically or to generate typed clients.

## Options

None.

## Example

```bash
gazepy schema
```

**Partial output:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AnalysisResult",
  "type": "object",
  "properties": {
    "functions": {
      "type": "array",
      "items": { "$ref": "#/definitions/FunctionTarget" }
    }
  }
}
```

Save to a file for use with validators:

```bash
gazepy schema > analysis-result.schema.json
```
