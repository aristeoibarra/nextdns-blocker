use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum NextdnsCommands {
    /// List active NextDNS categories and services
    List(NextdnsListArgs),
    /// Add a NextDNS native category
    AddCategory(NextdnsAddCategoryArgs),
    /// Remove a NextDNS native category
    RemoveCategory(NextdnsRemoveCategoryArgs),
    /// Add a NextDNS native service
    AddService(NextdnsAddServiceArgs),
    /// Remove a NextDNS native service
    RemoveService(NextdnsRemoveServiceArgs),
    /// List available NextDNS categories
    Categories(NextdnsCategoriesArgs),
    /// List available NextDNS services
    Services(NextdnsServicesArgs),
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
pub struct NextdnsAddServiceArgs {
    /// Service ID (e.g., "tiktok", "netflix")
    pub id: String,
}

#[derive(Args)]
pub struct NextdnsRemoveServiceArgs {
    /// Service ID
    pub id: String,
}

#[derive(Args)]
pub struct NextdnsCategoriesArgs {}

#[derive(Args)]
pub struct NextdnsServicesArgs {}
