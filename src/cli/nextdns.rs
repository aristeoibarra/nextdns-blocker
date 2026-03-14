use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum NextdnsCommands {
    /// List active NextDNS categories
    List(NextdnsListArgs),
    /// Add a NextDNS native category
    AddCategory(NextdnsAddCategoryArgs),
    /// Remove a NextDNS native category
    RemoveCategory(NextdnsRemoveCategoryArgs),
    /// List available NextDNS categories
    Categories(NextdnsCategoriesArgs),
}

#[derive(Args)]
pub struct NextdnsListArgs {}

#[derive(Args)]
pub struct NextdnsAddCategoryArgs {
    /// Category ID (e.g., "gambling", "porn")
    pub id: String,
}

#[derive(Args)]
pub struct NextdnsRemoveCategoryArgs {
    /// Category ID
    pub id: String,
}

#[derive(Args)]
pub struct NextdnsCategoriesArgs {}
