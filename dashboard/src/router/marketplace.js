export default [
	{
		path: '/install-app/:marketplaceApp',
		name: 'InstallMarketplaceApp',
		component: () => import('@/views/InstallMarketplaceApp.vue'),
		props: true
	},
	{
		path: '/user-review/:marketplaceApp',
		name: 'ReviewMarketplaceApp',
		component: () => import('@/views/ReviewMarketplaceApp.vue'),
		props: true
	},
	{
		path: '/marketplace',
		name: 'Marketplace',
		component: () =>
			import(/* webpackChunkName: "marketplace" */ '../views/Marketplace.vue'),
		children: [
			{
				path: 'publisher-profile',
				component: () =>
					import(
						/* webpackChunkName: "marketplace" */ '../views/marketplace/MarketplacePublisherProfile.vue'
					)
			},
			{
				path: 'apps',
				component: () =>
					import(
						/* webpackChunkName: "marketplace" */ '../views/marketplace/MarketplaceApps.vue'
					)
			},
			{
				path: 'payouts',
				component: () =>
					import(
						/* webpackChunkName: "marketplace" */ '../views/marketplace/MarketplacePayouts.vue'
					)
			}
		]
	},
	{
		path: '/marketplace/apps/new',
		name: 'NewMarketplaceApp',
		component: () => import('../views/NewMarketplaceApp.vue'),
		props: true
	},
	{
		path: '/marketplace/apps/:appName',
		name: 'MarketplaceApp',
		component: () => import('../views/MarketplaceApp.vue'),
		props: true,
		children: [
			{
				name: 'MarketplaceAppOverview',
				path: 'overview',
				component: () => import('../views/MarketplaceAppOverview.vue')
			},
			{
				name: 'MarketplaceAppAnalytics',
				path: 'analytics',
				component: () => import('../views/MarketplaceAppAnalytics.vue')
			},
			{
				name: 'MarketplaceAppDeployment',
				path: 'releases',
				component: () => import('../views/MarketplaceAppDeployment.vue')
			},
			{
				name: 'MarketplaceAppSubscriptions',
				path: 'subscriptions',
				component: () => import('../views/MarketplaceAppSubscriptions.vue')
			},
			{
				name: 'MarketplaceAppPricing',
				path: 'pricing',
				component: () => import('../views/MarketplaceAppPricing.vue')
			}
		]
	}
];
