#!/usr/bin/env Rscript
# Extract team name mappings from R packages for import into our database
#
# This script exports team name variants from ncaahoopR, hoopR, and toRvik
# packages into CSV/JSON formats that can be imported using
# import_standardized_team_mappings.py
#
# Usage:
#   Rscript scripts/extract_r_package_mappings.R [package_name]
#
# Packages: ncaahoopr, hoopr, torvik, all

library(jsonlite)

extract_ncaahoopr <- function() {
    cat("Extracting ncaahoopR dict dataset...\n")
    
    # Check if package is installed
    if (!requireNamespace("devtools", quietly = TRUE)) {
        cat("Installing devtools...\n")
        install.packages("devtools")
    }
    
    if (!requireNamespace("ncaahoopR", quietly = TRUE)) {
        cat("Installing ncaahoopR from GitHub...\n")
        devtools::install_github("lbenz730/ncaahoopR")
    }
    
    library(ncaahoopR)
    data(dict)
    
    # Export to CSV
    output_file <- "ncaahoopr_dict.csv"
    write.csv(dict, output_file, row.names = FALSE)
    cat(sprintf("✓ Exported ncaahoopR dict to %s\n", output_file))
    cat(sprintf("  Rows: %d, Columns: %d\n", nrow(dict), ncol(dict)))
    
    return(output_file)
}

extract_hoopr <- function() {
    cat("Extracting hoopR teams_links dataset...\n")
    
    # Check if package is installed
    if (!requireNamespace("hoopR", quietly = TRUE)) {
        cat("Installing hoopR from CRAN...\n")
        install.packages("hoopR")
    }
    
    library(hoopR)
    
    # Try to load teams_links data
    # Note: teams_links might be in a different location or need to be fetched
    if (exists("teams_links", envir = asNamespace("hoopR"))) {
        data(teams_links)
    } else {
        # Alternative: try to get teams data
        cat("teams_links not found, trying to fetch teams data...\n")
        # This is a placeholder - actual implementation depends on hoopR API
        teams_links <- list()
        cat("⚠️  teams_links dataset not available in this version of hoopR\n")
        cat("   You may need to manually extract KenPom/ESPN mappings\n")
        return(NULL)
    }
    
    # Export to JSON
    output_file <- "hoopr_teams_links.json"
    write_json(teams_links, output_file, pretty = TRUE)
    cat(sprintf("✓ Exported hoopR teams_links to %s\n", output_file))
    
    return(output_file)
}

extract_torvik <- function() {
    cat("Extracting toRvik/cbbdata team names...\n")
    
    # Check if package is installed
    if (!requireNamespace("devtools", quietly = TRUE)) {
        cat("Installing devtools...\n")
        install.packages("devtools")
    }
    
    if (!requireNamespace("toRvik", quietly = TRUE)) {
        cat("Installing toRvik from GitHub...\n")
        devtools::install_github("andreweatherman/toRvik")
    }
    
    library(toRvik)
    
    # Get teams data
    tryCatch({
        teams <- cbd_teams()
        output_file <- "torvik_teams.csv"
        write.csv(teams, output_file, row.names = FALSE)
        cat(sprintf("✓ Exported toRvik teams to %s\n", output_file))
        cat(sprintf("  Rows: %d\n", nrow(teams)))
        return(output_file)
    }, error = function(e) {
        cat(sprintf("⚠️  Error extracting toRvik data: %s\n", e$message))
        cat("   You may need to check the toRvik package documentation\n")
        return(NULL)
    })
}

main <- function() {
    args <- commandArgs(trailingOnly = TRUE)
    package <- if (length(args) > 0) args[1] else "all"
    
    cat("=" %+% strrep("=", 60) %+% "\n")
    cat("R Package Team Mapping Extractor\n")
    cat("=" %+% strrep("=", 60) %+% "\n\n")
    
    results <- list()
    
    if (package == "all" || package == "ncaahoopr") {
        results$ncaahoopr <- extract_ncaahoopr()
        cat("\n")
    }
    
    if (package == "all" || package == "hoopr") {
        results$hoopr <- extract_hoopr()
        cat("\n")
    }
    
    if (package == "all" || package == "torvik") {
        results$torvik <- extract_torvik()
        cat("\n")
    }
    
    cat("=" %+% strrep("=", 60) %+% "\n")
    cat("Extraction complete!\n\n")
    cat("Next steps:\n")
    cat("1. Review the exported files\n")
    cat("2. Run import_standardized_team_mappings.py to import into database\n")
    cat("   Example:\n")
    cat("   python services/prediction-service-python/scripts/import_standardized_team_mappings.py \\\n")
    cat("       --source ncaahoopr --input ncaahoopr_dict.csv\n")
    cat("=" %+% strrep("=", 60) %+% "\n")
}

# Fix string concatenation (R doesn't have + for strings)
`%+%` <- function(a, b) paste0(a, b)

if (!interactive()) {
    main()
}
