using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using DTDLParser;

internal static class Program
{
    private sealed record Issue(
        string severity,
        string code,
        string message,
        string? dtmi = null,
        string? path = null
    );

    private sealed record Result(List<Issue> issues);

    public static int Main(string[] args)
    {
        try
        {
            var inputPath = GetArgValue(args, "--input");
            var outPath = GetArgValue(args, "--out"); // optional

            if (string.IsNullOrWhiteSpace(inputPath))
            {
                WriteUsage();
                return 1;
            }

            var jsonFiles = DiscoverJsonFiles(inputPath).ToList();
            if (jsonFiles.Count == 0)
            {
                var empty = new Result(new List<Issue>
                {
                    new Issue(
                        severity: "error",
                        code: "no_input_files",
                        message: $"No .json files found under input '{inputPath}'."
                    )
                });

                WriteResult(empty, outPath);
                return 2;
            }

            var modelTexts = new List<string>(capacity: jsonFiles.Count);
            foreach (var file in jsonFiles)
            {
                // Read as UTF-8; tolerate BOM etc.
                var text = File.ReadAllText(file, Encoding.UTF8);
                modelTexts.Add(text);
            }

            var parser = new ModelParser();

            try
            {
                // Authoritative parse/validate. If invalid, throws ParsingException.
                _ = parser.Parse(modelTexts);

                // If no exception, no errors.
                var ok = new Result(new List<Issue>());
                WriteResult(ok, outPath);
                return 0;
            }
            catch (ParsingException ex)
            {
                var issues = new List<Issue>();

                // Map DTDLParser errors into our stable DTO shape.
                foreach (var err in ex.Errors)
                {
                    // ValidationID is a machine-readable code (when present).
                    // PrimaryID is often the dtmi involved (when present).
                    var code = SafeToString(err.ValidationID) ?? "dtdl_parse_error";
                    var dtmi = SafeToString(err.PrimaryID);

                    // We usually don't get a JSON pointer path from the parser;
                    // keep null for now (compatible with Python DTO).
                    issues.Add(new Issue(
                        severity: "error",
                        code: code,
                        message: err.Message,
                        dtmi: dtmi,
                        path: null
                    ));
                }

                var result = new Result(issues);
                WriteResult(result, outPath);

                // Errors found
                return 2;
            }
        }
        catch (Exception ex)
        {
            // Tool failure (IO, unexpected crash, invalid args, etc.)
            var fail = new Result(new List<Issue>
            {
                new Issue(
                    severity: "error",
                    code: "tool_failure",
                    message: ex.ToString()
                )
            });

            // Try stdout if out file fails.
            try { WriteResult(fail, GetArgValue(args, "--out")); }
            catch { Console.Error.WriteLine(ex); }

            return 1;
        }
    }

    private static IEnumerable<string> DiscoverJsonFiles(string inputPath)
    {
        if (File.Exists(inputPath))
        {
            if (string.Equals(Path.GetExtension(inputPath), ".json", StringComparison.OrdinalIgnoreCase))
                return new[] { inputPath };
            return Array.Empty<string>();
        }

        if (Directory.Exists(inputPath))
        {
            return Directory.EnumerateFiles(inputPath, "*.json", SearchOption.AllDirectories);
        }

        return Array.Empty<string>();
    }

    private static void WriteResult(Result result, string? outPath)
    {
        var json = JsonSerializer.Serialize(
            result,
            new JsonSerializerOptions
            {
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });

        if (!string.IsNullOrWhiteSpace(outPath))
        {
            File.WriteAllText(outPath, json, Encoding.UTF8);
        }
        else
        {
            Console.Out.WriteLine(json);
        }
    }

    private static string? GetArgValue(string[] args, string name)
    {
        for (var i = 0; i < args.Length; i++)
        {
            if (!string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                continue;

            if (i + 1 >= args.Length)
                return null;

            return args[i + 1];
        }

        return null;
    }

    private static string? SafeToString(object? value)
        => value?.ToString();

    private static void WriteUsage()
    {
        Console.Error.WriteLine("CyMiSE DTDL Validator (offline)");
        Console.Error.WriteLine();
        Console.Error.WriteLine("Usage:");
        Console.Error.WriteLine("  Cymise.DtdlValidator.Cli --input <fileOrFolder> [--out <result.json>]");
        Console.Error.WriteLine();
        Console.Error.WriteLine("Notes:");
        Console.Error.WriteLine("  --input can be a .json file or a folder (recursive *.json discovery).");
        Console.Error.WriteLine("  Outputs JSON: { \"issues\": [ ... ] } to stdout unless --out is provided.");
    }
}
