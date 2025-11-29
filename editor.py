    # 3) Sidebar: user settings only

    # --- Persistent defaults for modes and settings ---
    if "calculator_mode" not in st.session_state:
        st.session_state.calculator_mode = UserMode.RENTER.value

    # Owner defaults
    if "owner_maint_rate" not in st.session_state:
        st.session_state.owner_maint_rate = 0.55  # $/pt
    if "owner_discount_tier" not in st.session_state:
        st.session_state.owner_discount_tier = TIER_NO_DISCOUNT
    if "owner_inc_m" not in st.session_state:
        st.session_state.owner_inc_m = True
    if "owner_inc_c" not in st.session_state:
        st.session_state.owner_inc_c = True
    if "owner_inc_d" not in st.session_state:
        st.session_state.owner_inc_d = True
    if "owner_purchase_price" not in st.session_state:
        st.session_state.owner_purchase_price = 18.0  # $/pt
    if "owner_capital_cost_pct" not in st.session_state:
        st.session_state.owner_capital_cost_pct = 5.0  # %
    if "owner_salvage_value" not in st.session_state:
        st.session_state.owner_salvage_value = 3.0  # $/pt
    if "owner_useful_life" not in st.session_state:
        st.session_state.owner_useful_life = 10  # years

    # Renter defaults
    if "renter_cost_per_point" not in st.session_state:
        st.session_state.renter_cost_per_point = 0.50
    if "renter_discount_tier" not in st.session_state:
        st.session_state.renter_discount_tier = TIER_NO_DISCOUNT

    with st.sidebar:
        st.markdown("### 👤 User Profile")

        # Mode selector (shared for both)
        mode_sel = st.radio(
            "Mode:",
            [m.value for m in UserMode],
            key="calculator_mode",
            horizontal=True,
        )
        mode = UserMode(mode_sel)

        owner_params: Optional[dict] = None
        policy: DiscountPolicy = DiscountPolicy.NONE
        rate: float = 0.0

        st.divider()

        if mode == UserMode.OWNER:
            st.markdown("##### 💰 Owner Settings")

            # Maintenance rate (owner)
            rate = st.number_input(
                "Annual Maintenance Fee ($/point)",
                min_value=0.0,
                step=0.01,
                key="owner_maint_rate",
                help="Dollar cost per point for annual maintenance fees.",
            )

            # Owner discount tier
            owner_tier = st.radio(
                "Owner discount tier:",
                TIER_OPTIONS,
                key="owner_discount_tier",
            )

            with st.expander("🔧 Advanced Options", expanded=False):
                st.markdown("**Include in cost:**")
                inc_m = st.checkbox(
                    "Maintenance Fees",
                    key="owner_inc_m",
                    value=st.session_state.owner_inc_m,
                )
                inc_c = st.checkbox(
                    "Capital Cost",
                    key="owner_inc_c",
                    value=st.session_state.owner_inc_c,
                )
                inc_d = st.checkbox(
                    "Depreciation",
                    key="owner_inc_d",
                    value=st.session_state.owner_inc_d,
                )

                st.divider()
                st.markdown("**Purchase Details**")
                cap = st.number_input(
                    "Purchase Price ($/pt)",
                    min_value=0.0,
                    step=1.0,
                    key="owner_purchase_price",
                )
                coc_pct = st.number_input(
                    "Cost of Capital (%)",
                    min_value=0.0,
                    step=0.5,
                    key="owner_capital_cost_pct",
                )

                st.markdown("**Depreciation**")
                life = st.number_input(
                    "Useful Life (years)",
                    min_value=1,
                    step=1,
                    key="owner_useful_life",
                )
                salvage = st.number_input(
                    "Salvage Value ($/pt)",
                    min_value=0.0,
                    step=0.5,
                    key="owner_salvage_value",
                )

            # Map tier to discount policy & multiplier
            if "Executive" in owner_tier:
                policy = DiscountPolicy.EXECUTIVE
                disc_mul = 0.75
            elif "Presidential" in owner_tier or "Chairman" in owner_tier:
                policy = DiscountPolicy.PRESIDENTIAL
                disc_mul = 0.70
            else:
                policy = DiscountPolicy.NONE
                disc_mul = 1.0

            owner_params = {
                "disc_mul": disc_mul,
                "inc_m": st.session_state.owner_inc_m,
                "inc_c": st.session_state.owner_inc_c,
                "inc_d": st.session_state.owner_inc_d,
                "cap_rate": st.session_state.owner_purchase_price
                * (st.session_state.owner_capital_cost_pct / 100.0),
                "dep_rate": (
                    (st.session_state.owner_purchase_price - st.session_state.owner_salvage_value)
                    / st.session_state.owner_useful_life
                    if st.session_state.owner_useful_life > 0
                    else 0.0
                ),
            }

        else:
            st.markdown("##### 💵 Renter Settings")

            rate = st.number_input(
                "Cost per Point ($)",
                min_value=0.0,
                step=0.01,
                key="renter_cost_per_point",
                help="Dollar cost per point as charged by an Owner.",
            )

            renter_tier = st.radio(
                "Discount tier available:",
                TIER_OPTIONS,
                key="renter_discount_tier",
                help="Choose the highest rental discount the Owner will pass to you.",
            )
            if "Presidential" in renter_tier or "Chairman" in renter_tier:
                policy = DiscountPolicy.PRESIDENTIAL
            elif "Executive" in renter_tier:
                policy = DiscountPolicy.EXECUTIVE
            else:
                policy = DiscountPolicy.NONE

        st.divider()
