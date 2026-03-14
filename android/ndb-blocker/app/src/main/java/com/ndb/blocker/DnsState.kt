package com.ndb.blocker

data class DnsState(
    val customCategories: List<DnsCategory>,
    val uncategorized: List<DnsDomain>,
    val allowedDomains: List<DnsDomain>,
    val totalBlockedDomains: Int,
    val totalAllowedDomains: Int,
    val syncedAt: Long
)

data class DnsCategory(
    val name: String,
    val description: String?,
    val domains: List<String>,
    val count: Int
)

data class DnsDomain(
    val domain: String,
    val description: String?
)
