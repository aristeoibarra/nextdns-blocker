use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum CategoryCommands {
    /// Create a new category
    Create(CategoryCreateArgs),
    /// Delete a category
    Delete(CategoryDeleteArgs),
    /// List all categories
    List(CategoryListArgs),
    /// Show details of a category
    Show(CategoryShowArgs),
    /// Add a domain to a category
    AddDomain(CategoryAddDomainArgs),
    /// Remove a domain from a category
    RemoveDomain(CategoryRemoveDomainArgs),
}

#[derive(Args)]
pub struct CategoryCreateArgs {
    /// Category name
    pub name: String,

    /// Category description
    #[arg(long, short)]
    pub description: Option<String>,

    /// Schedule (JSON string)
    #[arg(long)]
    pub schedule: Option<String>,
}

#[derive(Args)]
pub struct CategoryDeleteArgs {
    /// Category name
    pub name: String,

    /// PIN for protected categories
    #[arg(long)]
    pub pin: Option<String>,
}

#[derive(Args)]
pub struct CategoryListArgs {}

#[derive(Args)]
pub struct CategoryShowArgs {
    /// Category name
    pub name: String,
}

#[derive(Args)]
pub struct CategoryAddDomainArgs {
    /// Category name
    pub category: String,

    /// Domains to add
    #[arg(required = true)]
    pub domains: Vec<String>,
}

#[derive(Args)]
pub struct CategoryRemoveDomainArgs {
    /// Category name
    pub category: String,

    /// Domains to remove
    #[arg(required = true)]
    pub domains: Vec<String>,
}
