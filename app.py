import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import date

# Set page configuration
st.set_page_config(
    page_title="ECH2O AOP Design Dashboard",
    page_icon="💧",
    layout="wide"
)

# Title and description
st.title("ECH2O AOP Design Dashboard")
st.markdown("This dashboard calculates and summarizes the design specifications for a modular wastewater treatment process.")

# Sidebar for design parameters
st.sidebar.header("Design Parameters")

flowrate = st.sidebar.number_input("Flowrate (cubic meters per day)", min_value=10.0, value=10.0, step=5.0, max_value=150.0)
cod_inlet = st.sidebar.number_input("COD Inlet (ppm)", min_value=10.0, value=1000.0, step=10.0)
cod_target = st.sidebar.number_input("COD Target (ppm)", min_value=1.0, max_value=cod_inlet-1.0, value=min(75.0, cod_inlet-1.0), step=5.0)
initial_ph = st.sidebar.number_input("Initial pH", min_value=1.0, max_value=14.0, value=7.0, step=0.1)
reactor_size_options = {1.5: "1.5 cubic meters", 2.0: "2.0 cubic meters"}
reactor_size = st.sidebar.selectbox(
    "AOP Reactor Size", 
    options=list(reactor_size_options.keys()),
    format_func=lambda x: reactor_size_options[x]
)

# Add PHP conversion rate
php_conversion_rate = st.sidebar.number_input("USD to PHP Conversion Rate", min_value=40.0, max_value=80.0, value=58.0, step=0.1)

# Create a separator in the sidebar
st.sidebar.markdown("---")
st.sidebar.header("Cost Parameters")

# Add sidebar section for electricity and chemical costs
electricity_cost = st.sidebar.number_input("Electricity Cost (USD/kWh)", min_value=0.05, max_value=0.5, value=0.19, step=0.01)
chemical_cost_factor = st.sidebar.number_input("Chemical Cost Factor (1.0 = standard)", min_value=0.5, max_value=2.0, value=1.0, step=0.1)

# Main content
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "AOP Summary", 
    "Wastewater Conveyance", 
    "Filtration Requirements", 
    "pH Adjustment", 
    "Standard Rates",
    "Full Design Summary",
    "CAPEX & OPEX"
])

# Calculate design values
def calculate_design_values(aop_reactor_unit_cost, pump_unit_cost, filter_unit_cost, ph_adjustment_unit_cost, ozone_generator_unit_cost, operator_monthly_salary, ozone_power_consumption, pump_power_consumption, chemicals_base_cost, maintenance_factor, piping_factor, epc_factor, container_20ft_cost, container_40ft_cost):
    # Basic calculations
    cod_load_kg_per_day = flowrate * cod_inlet / 1000  # kg/day
    ozone_requirement_kg_per_day = 0.25 * cod_load_kg_per_day  # 0.25 g O3 per 1 g COD
    
    # AOP reactor calculations
    reactor_volume_per_day = flowrate  # m³/day
    reactor_volume_per_hour = reactor_volume_per_day / 24  # m³/hour
    
    # Each reactor can process 1 reactor_size volume in 2 hours
    hourly_processing_capacity_per_reactor = reactor_size / 2  # m³/hour
    
    # Number of reactors needed based on flow rate
    num_parallel_reactors_needed = np.ceil(reactor_volume_per_hour / hourly_processing_capacity_per_reactor)
    
    # Calculate ozone generators
    ozone_requirement_g_per_hour = ozone_requirement_kg_per_day * 1000 / 24  # g/hour
    ozone_capacity_per_generator = 200  # g/hour
    ozone_capacity_per_reactor = 2 * ozone_capacity_per_generator  # 2 generators per reactor
    
    # Determine number of reactor trains
    # Calculate stage-wise COD reduction
    current_cod = cod_inlet
    stages_needed = 0
    cod_values = [current_cod]
    
    while current_cod > cod_target:
        current_cod = current_cod * 0.40  # 60% reduction
        cod_values.append(current_cod)
        stages_needed += 1
    
    # Ensure min 2 reactors, max 4 reactors per train
    stages_needed = max(2, min(4, stages_needed))
    
    # Number of reactor trains
    num_reactor_trains = int(np.ceil(num_parallel_reactors_needed))
    
    # Total number of reactors
    total_reactors = num_reactor_trains * stages_needed
    
    # Ozone generator calculations
    num_ozone_generators = total_reactors * 2  # 2 generators per reactor
    ozone_generator_cost = num_ozone_generators * ozone_generator_unit_cost  # Variable cost per generator
    
    # Pump calculations
    pump_flow_rate_per_train = reactor_size / 0.25  # m³/hour (fill in 15 minutes = 0.25 hours)
    total_pump_flow_rate = pump_flow_rate_per_train * num_reactor_trains  # m³/hour
    
    # Recirculation pump calculations
    # Rate of recirculation = # of AOP reactors × volume of reactors × 5 / 2 hrs
    recirculation_flow_rate = total_reactors * reactor_size * 5 / 2  # m³/hour
    recirculation_pumps_required = 2  # 1 running, 1 standby
    
    # CAPEX calculations
    aop_reactor_cost = aop_reactor_unit_cost * total_reactors
    
    total_influent_effluent_pumps = num_reactor_trains * 4  # 2 influent (1 running, 1 standby) + 2 effluent per train
    total_pumps = total_influent_effluent_pumps + recirculation_pumps_required
    pump_cost = pump_unit_cost * total_pumps
    
    # Sand filtration system cost
    filtration_loading_rate = 10  # m³/m²/hour (typical value)
    required_filter_area = total_pump_flow_rate / filtration_loading_rate
    filter_units = max(2, int(np.ceil(required_filter_area/5)))
    filter_cost = filter_unit_cost * required_filter_area
    
    # pH adjustment systems
    ph_adjustment_cost = ph_adjustment_unit_cost  # Variable cost for pH systems
    
    # Container housing calculations
    total_equipment_units = total_reactors + filter_units
    
    # Container requirements based on flowrate and equipment count
    container_20ft_capacity = 6  # units
    container_40ft_capacity = 12  # units
    # Note: container costs now come from user input in tab5
    
    if flowrate <= 15:
        # Use 20ft container for flowrates up to 15 m³/day
        num_20ft_containers = 1
        num_40ft_containers = 0
    else:
        # For flowrates > 15 m³/day, start with 40ft containers
        if total_equipment_units <= container_40ft_capacity:
            num_40ft_containers = 1
            num_20ft_containers = 0
        else:
            # Need multiple containers
            num_40ft_containers = total_equipment_units // container_40ft_capacity
            remaining_units = total_equipment_units % container_40ft_capacity
            
            # Determine if we need additional 20ft or 40ft container
            if remaining_units > 0:
                if remaining_units <= container_20ft_capacity:
                    num_20ft_containers = 1
                else:
                    num_40ft_containers += 1
                    num_20ft_containers = 0
            else:
                num_20ft_containers = 0
    
    container_cost = (num_20ft_containers * container_20ft_cost) + (num_40ft_containers * container_40ft_cost)
    
    # Piping, instrumentation, and controls
    piping_cost = (aop_reactor_cost + pump_cost) * piping_factor  # Using user-defined piping factor
    
    # Engineering, procurement, and construction (EPC)
    direct_costs = aop_reactor_cost + ozone_generator_cost + pump_cost + filter_cost + ph_adjustment_cost + piping_cost + container_cost
    epc_cost = direct_costs * epc_factor  # Using user-defined EPC factor
    
    # Total CAPEX
    total_capex = direct_costs + epc_cost
    
    # OPEX calculations (monthly)
    # Electricity for ozone generation
    daily_ozone_energy = ozone_requirement_kg_per_day * ozone_power_consumption  # kWh/day
    monthly_ozone_energy = daily_ozone_energy * 30  # kWh/month
    monthly_ozone_power_cost = monthly_ozone_energy * electricity_cost
    
    # Electricity for pumping (including recirculation)
    daily_pumping_energy = flowrate * pump_power_consumption  # kWh/day
    # Add recirculation energy (assume running 24 hours a day)
    daily_recirculation_energy = recirculation_flow_rate * 24 * pump_power_consumption  # kWh/day
    total_daily_pumping_energy = daily_pumping_energy + daily_recirculation_energy
    monthly_pumping_energy = total_daily_pumping_energy * 30  # kWh/month
    monthly_pumping_cost = monthly_pumping_energy * electricity_cost
    
    # Chemical costs for pH adjustment
    monthly_chemical_cost = (flowrate * 30) * chemicals_base_cost * chemical_cost_factor
    
    # Labor costs
    operators_required = max(1, int(np.ceil(total_reactors / 8)))  # Minimum 2 operators
    monthly_labor_cost = operators_required * operator_monthly_salary
    
    # Maintenance costs (parts, consumables)
    monthly_maintenance_cost = total_capex * maintenance_factor / 12  # Maintenance factor % of CAPEX per year
    
    # Total monthly OPEX
    total_monthly_opex = monthly_ozone_power_cost + monthly_pumping_cost + monthly_chemical_cost + monthly_labor_cost + monthly_maintenance_cost
    
    return {
        "flowrate": flowrate,
        "cod_inlet": cod_inlet,
        "cod_target": cod_target,
        "initial_ph": initial_ph,
        "reactor_size": reactor_size,
        "cod_load_kg_per_day": cod_load_kg_per_day,
        "ozone_requirement_kg_per_day": ozone_requirement_kg_per_day,
        "num_parallel_reactors_needed": num_parallel_reactors_needed,
        "stages_needed": stages_needed,
        "num_reactor_trains": num_reactor_trains,
        "total_reactors": total_reactors,
        "num_ozone_generators": num_ozone_generators,
        "ozone_generator_cost": ozone_generator_cost,
        "cod_reduction_stages": cod_values,
        "pump_flow_rate_per_train": pump_flow_rate_per_train,
        "total_pump_flow_rate": total_pump_flow_rate,
        "recirculation_flow_rate": recirculation_flow_rate,
        "recirculation_pumps_required": recirculation_pumps_required,
        "total_influent_effluent_pumps": total_influent_effluent_pumps,
        "total_pumps": total_pumps,
        "aop_reactor_cost": aop_reactor_cost,
        "pump_cost": pump_cost,
        "filter_cost": filter_cost,
        "filter_units": filter_units,
        "ph_adjustment_cost": ph_adjustment_cost,
        "piping_cost": piping_cost,
        "epc_cost": epc_cost,
        "total_capex": total_capex,
        "monthly_ozone_power_cost": monthly_ozone_power_cost,
        "daily_recirculation_energy": daily_recirculation_energy,
        "monthly_pumping_cost": monthly_pumping_cost,
        "monthly_chemical_cost": monthly_chemical_cost,
        "monthly_labor_cost": monthly_labor_cost,
        "monthly_maintenance_cost": monthly_maintenance_cost,
        "total_monthly_opex": total_monthly_opex,
        "electricity_cost": electricity_cost,
        "chemical_cost_factor": chemical_cost_factor,
        "operators_required": operators_required,
        "php_conversion_rate": php_conversion_rate,
        "num_20ft_containers": num_20ft_containers,
        "num_40ft_containers": num_40ft_containers,
        "container_cost": container_cost,
        "total_equipment_units": total_equipment_units
    }

# Tab 5: Standard Rates
with tab5:
    st.header("Standard Cost Rates")
    st.write("Adjust standard cost rates used in the calculations. All final costs will be reported in Philippine Pesos (PHP).")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Equipment Costs")
        aop_reactor_unit_cost = st.number_input("AOP Reactor Cost (USD)", min_value=500.0, max_value=1000.0, value=650.0, step=50.0)
        pump_unit_cost = st.number_input("Pump Unit Cost (USD)", min_value=500.0, max_value=1000.0, value=650.0, step=50.0)
        filter_unit_cost = st.number_input("Filter Cost per m² (USD)", min_value=500.0, max_value=1000.0, value=650.0, step=50.0)
        ph_adjustment_unit_cost = st.number_input("pH Adjustment System Cost (USD)", min_value=500.0, max_value=1000.0, value=650.0, step=50.0)
        ozone_generator_unit_cost = st.number_input("Ozone Generator Unit Cost (USD)", min_value=500.0, max_value=1000.0, value=650.0, step=50.0)
        
        st.subheader("Container Housing Costs")
        container_20ft_cost = st.number_input("20ft Container Cost (USD)", min_value=4000.0, max_value=8000.0, value=6000.0, step=500.0)
        container_40ft_cost = st.number_input("40ft Container Cost (USD)", min_value=5000.0, max_value=10000.0, value=7000.0, step=500.0)
    
    with col2:
        st.subheader("Operational Costs and Factors")
        operator_monthly_salary = st.number_input("Operator Monthly Salary (USD)", min_value=300.0, max_value=1000.0, value=450.0, step=50.0)
        ozone_power_consumption = st.number_input("Ozone Power Consumption (kWh per kg)", min_value=1.0, max_value=5.0, value=3.0, step=0.5)
        pump_power_consumption = st.number_input("Pump Power Consumption (kWh per m³)", min_value=0.03, max_value=0.15, value=0.05, step=0.01)
        chemicals_base_cost = st.number_input("Chemical Base Cost (USD per m³)", min_value=0.1, max_value=1.0, value=0.25, step=0.05)
        maintenance_factor = st.number_input("Maintenance Cost (% of CAPEX per year)", min_value=2.5, max_value=15.0, value=10.0, step=0.5)
    
    st.subheader("Engineering and Construction Factors")
    col1, col2 = st.columns(2)
    
    with col1:
        piping_factor = st.number_input("Piping Cost (% of equipment cost)", min_value=20.0, max_value=40.0, value=30.0, step=5.0) / 100.0
    
    with col2:
        epc_factor = st.number_input("EPC Factor (% of direct costs)", min_value=20.0, max_value=60.0, value=30.0, step=5.0) / 100.0
        
    # Information about PHP conversion
    st.info(f"The USD to PHP conversion rate is currently set to: {php_conversion_rate:.2f} PHP per USD. All cost displays in this dashboard will be shown in Philippine Pesos (PHP).")

# Calculate design values using the user-adjusted standard rates from tab 5
design_values = calculate_design_values(
    aop_reactor_unit_cost, 
    pump_unit_cost, 
    filter_unit_cost, 
    ph_adjustment_unit_cost, 
    ozone_generator_unit_cost, 
    operator_monthly_salary, 
    ozone_power_consumption, 
    pump_power_consumption, 
    chemicals_base_cost, 
    maintenance_factor / 100.0,  # Convert from percentage to decimal
    piping_factor, 
    epc_factor,
    container_20ft_cost,  # Add container costs
    container_40ft_cost
)

# Define CAPEX and OPEX items for display
capex_items = {
    "AOP Reactors": design_values['aop_reactor_cost'],
    "Ozone Generators": design_values['ozone_generator_cost'],
    "Pumping Equipment": design_values['pump_cost'],
    "Sand Filtration": design_values['filter_cost'],
    "pH Adjustment": design_values['ph_adjustment_cost'],
    "Container Housing": design_values['container_cost'],
    "Piping & Instrumentation": design_values['piping_cost'],
    "EPC": design_values['epc_cost']
}

opex_items = {
    "Ozone Generation Power": design_values['monthly_ozone_power_cost'],
    "Pumping Power": design_values['monthly_pumping_cost'],
    "Chemicals": design_values['monthly_chemical_cost'],
    "Labor": design_values['monthly_labor_cost'],
    "Maintenance": design_values['monthly_maintenance_cost']
}


# Tab 1: AOP Summary (Redesigned as a comprehensive landing page)
with tab1:
    st.header("ECH2O Advanced Oxidation Process Design Summary")
    
    # Design overview at the top
    st.markdown(f"""
    ### Design Overview for {design_values['flowrate']:.1f} m³/day Wastewater Treatment Plant
    This dashboard summarizes the complete design for a modular Advanced Oxidation Process (AOP) wastewater treatment 
    system configured for {design_values['cod_inlet']:.0f} ppm inlet COD with a target of {design_values['cod_target']:.0f} ppm outlet COD.
    """)
    
    # Create 3 columns for the key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total AOP Reactors", f"{design_values['total_reactors']}")
        st.metric("Total Pumps", f"{design_values['total_pumps']}")
        
    with col2:
        st.metric("COD Reduction", f"{100 * (1 - design_values['cod_target']/design_values['cod_inlet']):.1f}%")
        st.metric("Total Housed Units", f"{design_values['total_equipment_units']}")
        
    with col3:
        if design_values['num_20ft_containers'] > 0:
            st.metric("20ft Containers", f"{design_values['num_20ft_containers']}")
        if design_values['num_40ft_containers'] > 0:
            st.metric("40ft Containers", f"{design_values['num_40ft_containers']}")
            
    with col4:
        total_capex_php = design_values['total_capex'] * design_values['php_conversion_rate']
        total_monthly_opex_php = design_values['total_monthly_opex'] * design_values['php_conversion_rate']
        
        # Calculate Total Bid Price + Tax & Contingency
        contingency_php = total_capex_php * 0.1
        tax_php = total_capex_php * 1.1 * 0.12
        total_bid_price_php = total_capex_php + tax_php + contingency_php
        
        st.metric("Total Bid Price", f"₱{total_bid_price_php:,.0f}")
        st.metric("Monthly OPEX", f"₱{total_monthly_opex_php:,.0f}")
    
    # Horizontal divider
    st.markdown("---")
    
    # Create tabs within the summary page
    summary_tabs = st.tabs(["Process Overview", "Equipment Summary", "System Performance"])
    
    # Tab 1: Process Overview
    with summary_tabs[0]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("COD Treatment Process")
            st.metric("Initial COD", f"{design_values['cod_inlet']:.2f} ppm")
            st.metric("Target COD", f"{design_values['cod_target']:.2f} ppm")
            st.metric("COD Load", f"{design_values['cod_load_kg_per_day']:.2f} kg/day")
            st.metric("Ozone Requirement", f"{design_values['ozone_requirement_kg_per_day']:.2f} kg/day")
            
            # System schematic
            st.subheader("System Schematic")
            
            schematic = """
            Raw Wastewater → pH Adjustment (to 9.5) → AOP Reactor Trains → Sand Filtration → pH Adjustment (to 7.0) → Treated Effluent
                                                        |       ↑
                                                        v       |
                                                    Each train: |
                                                    [AOP 1] → [AOP 2] → ... → [AOP n]
                                                        ↑_______|_______↓
                                                            Recirculation
            """
            
            st.code(schematic)
            
        with col2:
            # Show COD reduction stages
            st.subheader("COD Reduction by Stage")
            cod_data = pd.DataFrame({
                "Stage": [f"Stage {i}" if i > 0 else "Inlet" for i in range(len(design_values['cod_reduction_stages']))],
                "COD (ppm)": [f"{cod:.2f}" for cod in design_values['cod_reduction_stages']],
                "Reduction (%)": ["0%"] + [f"{100 * (1 - design_values['cod_reduction_stages'][i]/design_values['cod_reduction_stages'][i-1]):.1f}%" 
                               for i in range(1, len(design_values['cod_reduction_stages']))]
            })
            st.table(cod_data)
            
            # pH adjustment overview
            st.subheader("pH Adjustment")
            st.metric("Initial pH", f"{design_values['initial_ph']}")
            st.metric("Pre-AOP Target pH", "9.5")
            st.metric("Post-Filtration Target pH", "7.0")
            
            if design_values['initial_ph'] < 9.5:
                ph_change = 9.5 - design_values['initial_ph']
                st.write(f"Need to raise initial pH by {ph_change:.1f} units")
            elif design_values['initial_ph'] > 9.5:
                ph_change = design_values['initial_ph'] - 9.5
                st.write(f"Need to lower initial pH by {ph_change:.1f} units")
    
    # Tab 2: Equipment Summary
    with summary_tabs[1]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Reactor Configuration")
            st.metric("AOP Reactor Size", f"{design_values['reactor_size']} m³")
            st.metric("AOP Reactors per Train", f"{design_values['stages_needed']}")
            st.metric("Reactor Trains Required", f"{design_values['num_reactor_trains']}")
            st.metric("Total AOP Reactors", f"{design_values['total_reactors']}")
            st.metric("Total Ozone Generators", f"{design_values['num_ozone_generators']}")
            
            # Reactor train diagram
            st.subheader("Reactor Train Configuration")
            st.write("Each train consists of AOP reactors connected in series:")
            
            diagram = ""
            for i in range(design_values['stages_needed']):
                if i == 0:
                    diagram += "Influent → [AOP Reactor 1] → "
                elif i == design_values['stages_needed'] - 1:
                    diagram += "[AOP Reactor " + str(i+1) + "] → Effluent"
                else:
                    diagram += "[AOP Reactor " + str(i+1) + "] → "
            
            st.code(diagram)
            st.write("Note: The last reactor in each train connects to the preceding reactor via gravity flow.")
            
        with col2:
            st.subheader("Pump Configuration")
            st.metric("Influent Pumps", f"{design_values['num_reactor_trains'] * 2}")
            st.metric("Effluent Pumps", f"{design_values['num_reactor_trains'] * 2}")
            st.metric("Recirculation Pumps", f"{design_values['recirculation_pumps_required']}")
            st.metric("Total Pumps", f"{design_values['total_pumps']}")
            st.metric("Pump Flow Rate (per train)", f"{design_values['pump_flow_rate_per_train']:.2f} m³/hour")
            st.metric("Recirculation Flow Rate", f"{design_values['recirculation_flow_rate']:.2f} m³/hour")
            
            # Pump diagram
            st.subheader("Pump Configuration Diagram")
            pump_diagram = """
            Influent Storage → [Influent Pumps] → AOP Reactor Trains → [Effluent Pumps] → Effluent Storage
                                                       ↑       ↓
                                                [Recirculation Pumps]
            """
            st.code(pump_diagram)
        
        # Container housing information
        st.subheader("Container Housing Requirements")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Equipment Units", f"{design_values['total_equipment_units']}")
            st.write(f"(AOP Reactors + Filters)")
            
        with col2:
            if design_values['num_20ft_containers'] > 0:
                st.metric("20ft Containers", f"{design_values['num_20ft_containers']}")
                st.write("Each 20ft container houses up to 6 equipment units")
            
        with col3:
            if design_values['num_40ft_containers'] > 0:
                st.metric("40ft Containers", f"{design_values['num_40ft_containers']}")
                st.write("Each 40ft container houses up to 12 equipment units")
                
        st.info(f"""
        Container housing information:
        - Each 20ft container costs $6,000 and can house up to 6 equipment units (reactors or filters)
        - Each 40ft container costs $7,000 and can house up to 12 equipment units (reactors or filters)
        - For flowrates ≤15 m³/day, 20ft containers are used
        - For flowrates >15 m³/day, 40ft containers are used primarily
        - Additional equipment is housed in either 20ft or 40ft containers based on the count
        """)
        
        # Filtration information
        st.subheader("Filtration System")
        st.metric("Required Filter Area", f"{design_values['total_pump_flow_rate'] / 10:.2f} m²")
        st.metric("Filter Units", f"{design_values['filter_units']}")
    
    # Tab 3: System Performance
    with summary_tabs[2]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Energy Requirements")
            st.metric("Ozone Generation", f"{design_values['ozone_requirement_kg_per_day'] * 3:.2f} kWh/day")
            st.metric("Pumping", f"{design_values['flowrate'] * 0.05:.2f} kWh/day")
            st.metric("Recirculation", f"{design_values['daily_recirculation_energy']:.2f} kWh/day")
            
            total_daily_energy = (design_values['ozone_requirement_kg_per_day'] * 3) + \
                                (design_values['flowrate'] * 0.05) + \
                                design_values['daily_recirculation_energy']
            
            st.metric("Total Daily Energy", f"{total_daily_energy:.2f} kWh/day")
            st.metric("Monthly Energy Cost", f"₱{design_values['monthly_ozone_power_cost'] * design_values['php_conversion_rate'] + design_values['monthly_pumping_cost'] * design_values['php_conversion_rate']:,.2f}")
            
        with col2:
            st.subheader("Cost Summary")
            
            # Display simplified CAPEX and OPEX
            capex_php = design_values['total_capex'] * design_values['php_conversion_rate']
            monthly_opex_php = design_values['total_monthly_opex'] * design_values['php_conversion_rate']
            annual_opex_php = monthly_opex_php * 12
            
            st.metric("Total CAPEX", f"₱{capex_php:,.2f}")
            st.metric("Monthly OPEX", f"₱{monthly_opex_php:,.2f}")
            st.metric("Annual OPEX", f"₱{annual_opex_php:,.2f}")
            
            # Calculate cost per cubic meter
            daily_cost = monthly_opex_php / 30
            cost_per_m3 = daily_cost / design_values['flowrate']
            
            st.metric("Treatment Cost", f"₱{cost_per_m3:.2f}/m³")
            
    # Add final note about detailed information
    st.markdown("---")
    st.info("For detailed information on specific system components, please see the respective tabs above.")



# Tab 2: Wastewater Conveyance
with tab2:
    st.header("Wastewater Conveyance (Pump Requirements)")
    
    st.info("""
    **Pump Configuration:**
    - Each conveyance requires 1 running and 1 standby configuration.
    - Influent pumps fill the first reactors in each train simultaneously in 15 minutes.
    - Effluent pumps drain the last reactors in each train simultaneously in 15 minutes.
    - Recirculation pumps continuously recirculate AOP reactor volumes.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Influent Pumps")
        st.metric("Number of Pump Trains", f"{design_values['num_reactor_trains']}")
        st.metric("Pumps per Train", "2 (1 running, 1 standby)")
        st.metric("Total Influent Pumps", f"{design_values['num_reactor_trains'] * 2}")
        st.metric("Flow Rate per Pump", f"{design_values['pump_flow_rate_per_train']:.2f} m³/hour")
        st.metric("Total Influent Pump Capacity", f"{design_values['total_pump_flow_rate']:.2f} m³/hour")
    
    with col2:
        st.subheader("Effluent Pumps")
        st.metric("Number of Pump Trains", f"{design_values['num_reactor_trains']}")
        st.metric("Pumps per Train", "2 (1 running, 1 standby)")
        st.metric("Total Effluent Pumps", f"{design_values['num_reactor_trains'] * 2}")
        st.metric("Flow Rate per Pump", f"{design_values['pump_flow_rate_per_train']:.2f} m³/hour")
        st.metric("Total Effluent Pump Capacity", f"{design_values['total_pump_flow_rate']:.2f} m³/hour")
    
    with col3:
        st.subheader("Recirculation Pumps")
        st.metric("Total Recirculation Pumps", f"{design_values['recirculation_pumps_required']} (1 running, 1 standby)")
        st.metric("Recirculation Flow Rate", f"{design_values['recirculation_flow_rate']:.2f} m³/hour")
        st.metric("Recirculation Formula", "# AOP reactors × volume × 5 / 2 hrs")
        st.metric("Recirculation Energy", f"{design_values['daily_recirculation_energy']:.2f} kWh/day")
        
        # Explanation of recirculation
        st.info("""
        The recirculation pump train handles the continuous recirculation of AOP reactor volumes
        to ensure optimal treatment efficiency and mixing.
        """)

    # Summary of all pumps
    st.subheader("Total Pump Requirements")
    st.metric("Total Pumps Required", f"{design_values['total_pumps']}")
    st.metric("Total Pump Cost", f"${design_values['pump_cost']:,.2f}")
    
    # Pump diagram
    st.subheader("Pump Configuration Diagram")
    pump_diagram = """
    Influent Storage → [Influent Pumps] → AOP Reactor Trains → [Effluent Pumps] → Effluent Storage
                                               ↑       ↓
                                        [Recirculation Pumps]
    """
    st.code(pump_diagram)

# Tab 3: Filtration Requirements
with tab3:
    st.header("Filtration Requirements")
    
    st.info("""
    **Sand Filtration System:**
    - Sand filtration follows the AOP process to remove any remaining particulates.
    - Sizing is based on the total flow rate from all AOP reactor trains.
    """)
    
    st.metric("Total Flow to Filtration", f"{flowrate:.2f} m³/day")
    st.metric("Average Hourly Flow", f"{flowrate/24:.2f} m³/hour")
    st.metric("Peak Hourly Flow (Design)", f"{design_values['total_pump_flow_rate']:.2f} m³/hour")
    
    # Filtration design parameters
    filtration_loading_rate = 10  # m³/m²/hour (typical value)
    required_filter_area = design_values['total_pump_flow_rate'] / filtration_loading_rate
    
    st.metric("Required Filter Area", f"{required_filter_area:.2f} m²")
    st.metric("Recommended Filter Units", f"{max(2, int(np.ceil(required_filter_area/5)))}")
    
    st.write("**Note:** Sand filters should be designed with n+1 redundancy for maintenance purposes.")

# Tab 4: pH Adjustment
with tab4:
    st.header("pH Adjustment Requirements")
    
    st.info("""
    **pH Adjustment Process:**
    1. Inlet pH needs to be raised to 9.5 before the first AOP reactor
    2. pH needs to be neutralized back to 7.0 after sand filtration
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pre-AOP pH Adjustment")
        st.metric("Initial pH", f"{initial_ph}")
        st.metric("Target pH", "9.5")
        
        if initial_ph < 9.5:
            ph_change = 9.5 - initial_ph
            st.write(f"Need to raise pH by {ph_change:.1f} units")
            st.write("Recommended Chemical: Sodium Hydroxide (NaOH)")
        elif initial_ph > 9.5:
            ph_change = initial_ph - 9.5
            st.write(f"Need to lower pH by {ph_change:.1f} units")
            st.write("Recommended Chemical: Sulfuric Acid (H₂SO₄)")
        else:
            st.write("No pH adjustment needed")
    
    with col2:
        st.subheader("Post-Filtration pH Adjustment")
        st.metric("Post-AOP pH (estimated)", "9.5")
        st.metric("Target pH", "7.0")
        
        st.write("Need to lower pH by 2.5 units")
        st.write("Recommended Chemical: Carbon Dioxide (CO₂) or Sulfuric Acid (H₂SO₄)")
    
    st.subheader("pH Adjustment System Components")
    st.write("""
    - Chemical storage tanks with secondary containment
    - Chemical dosing pumps with flow-paced control
    - Inline pH monitoring equipment
    - Mixing systems at injection points
    - Safety equipment for chemical handling
    """)


# Tab 6: Full Design Summary
with tab6:
    st.header("Complete Design Summary")
    
    # Create four sections for the organized design summary
    section1, section2 = st.tabs(["Design Summary", "Design Specifications"])
    
    with section1:
        st.subheader("Design Parameters")
        
        # Create dataframes for each category to better organize the information
        design_params = {
            "Parameter": [
                "Flowrate",
                "COD Inlet",
                "COD Target",
                "COD Reduction",
                "Initial pH",
                "Pre-AOP Target pH",
                "Post-Filtration Target pH",
                "Design Date"
            ],
            "Value": [
                f"{design_values['flowrate']:.2f} m³/day",
                f"{design_values['cod_inlet']:.2f} ppm",
                f"{design_values['cod_target']:.2f} ppm",
                f"{100 * (1 - design_values['cod_target']/design_values['cod_inlet']):.1f}%",
                f"{design_values['initial_ph']:.1f}",
                "9.5",
                "7.0",
                date.today().strftime("%Y-%m-%d")
            ]
        }
        
        # Display design parameters table
        st.table(pd.DataFrame(design_params))
        
        st.subheader("Design Details")
        design_details = {
            "Parameter": [
                "COD Load",
                "Ozone Requirement",
                "Ozone Requirement per COD",
                "Required Filter Area",
                "Filtration Loading Rate",
                "Peak Flow Rate"
            ],
            "Value": [
                f"{design_values['cod_load_kg_per_day']:.2f} kg/day",
                f"{design_values['ozone_requirement_kg_per_day']:.2f} kg/day",
                "0.25 g O₃/g COD",
                f"{required_filter_area:.2f} m²",
                "10 m³/m²/hour",
                f"{design_values['total_pump_flow_rate']:.2f} m³/hour"
            ]
        }
        
        # Display design details table
        st.table(pd.DataFrame(design_details))
    
    with section2:
        st.subheader("Reactor & Reactor Train Details")
        
        reactor_details = {
            "Parameter": [
                "AOP Reactor Size",
                "AOP Reactors per Train",
                "Reactor Trains Required",
                "Total AOP Reactors",
                "Total Ozone Generators",
                "Ozone Generator Capacity",
                "Total Ozone Generation Capacity"
            ],
            "Value": [
                f"{design_values['reactor_size']:.1f} m³",
                f"{design_values['stages_needed']}",
                f"{design_values['num_reactor_trains']}",
                f"{design_values['total_reactors']}",
                f"{design_values['num_ozone_generators']}",
                "200 g/hour per generator",
                f"{design_values['num_ozone_generators'] * 200:.0f} g/hour"
            ]
        }
        
        # Display reactor details table
        st.table(pd.DataFrame(reactor_details))
        
        st.subheader("Pump & Pump Train Details")
        
        pump_details = {
            "Parameter": [
                "Influent Pumps",
                "Effluent Pumps",
                "Recirculation Pumps",
                "Total Pumps",
                "Pump Flow Rate (per train)",
                "Total Influent/Effluent Pump Capacity",
                "Recirculation Flow Rate",
                "Recirculation Rate Formula"
            ],
            "Value": [
                f"{design_values['num_reactor_trains'] * 2} (1 running, 1 standby per train)",
                f"{design_values['num_reactor_trains'] * 2} (1 running, 1 standby per train)",
                f"{design_values['recirculation_pumps_required']} (1 running, 1 standby)",
                f"{design_values['total_pumps']}",
                f"{design_values['pump_flow_rate_per_train']:.2f} m³/hour",
                f"{design_values['total_pump_flow_rate']:.2f} m³/hour",
                f"{design_values['recirculation_flow_rate']:.2f} m³/hour",
                "# of AOP reactors × volume of reactors × 5 / 2 hrs"
            ]
        }
        
        # Display pump details table
        st.table(pd.DataFrame(pump_details))
    
    # COD Reduction Stages 
    st.subheader("COD Reduction Stages")
    cod_data = pd.DataFrame({
        "Stage": [f"Stage {i}" if i > 0 else "Inlet" for i in range(len(design_values['cod_reduction_stages']))],
        "COD (ppm)": [f"{cod:.2f}" for cod in design_values['cod_reduction_stages']],
        "Reduction (%)": ["0%"] + [f"{100 * (1 - design_values['cod_reduction_stages'][i]/design_values['cod_reduction_stages'][i-1]):.1f}%" 
                                   for i in range(1, len(design_values['cod_reduction_stages']))]
    })
    st.table(cod_data)
    
    # System Schematic with recirculation
    st.subheader("System Schematic")
    
    schematic = """
    Raw Wastewater → pH Adjustment (to 9.5) → AOP Reactor Trains → Sand Filtration → pH Adjustment (to 7.0) → Treated Effluent
                                                |       ↑
                                                v       |
                                            Each train: |
                                            [AOP 1] → [AOP 2] → ... → [AOP n]
                                                ↑_______|_______↓
                                                    Recirculation
    """
    
    st.code(schematic)
    
    st.subheader("Notes and Assumptions")
    st.write("""
    1. COD reduction per stage is assumed to be 60% (remaining COD is 40% of original).
    2. Ozone requirement is calculated at 0.25g O3 per 1g COD.
    3. Each AOP reactor is equipped with 2 ozone generators (200g O3/hour each).
    4. Each reactor train has a minimum of 2 and maximum of 4 reactors in series.
    5. Pump sizing assumes 15-minute fill/drain time for each reactor.
    6. The design includes 100% standby capacity for all pumps.
    7. Recirculation pumps continuously circulate water through the AOP reactors at a rate of 5× the total reactor volume every 2 hours.
    8. Filtration design uses standard loading rates for sand filtration.
    9. pH adjustment systems are sized based on typical chemical dosing requirements.
    """)
    
    # Download button for CSV
    # Create a combined dataframe for download
    combined_data = pd.concat([
        pd.DataFrame(design_params),
        pd.DataFrame(design_details),
        pd.DataFrame(reactor_details),
        pd.DataFrame(pump_details)
    ]).reset_index(drop=True)
    
    def convert_df_to_csv(df):
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    
    csv = convert_df_to_csv(combined_data)
    
    st.download_button(
        label="Download Complete Design Summary as CSV",
        data=csv,
        file_name="wastewater_treatment_complete_design_summary.csv",
        mime="text/csv",
    )

# Tab 7: CAPEX & OPEX
with tab7:
    st.header("CAPEX & OPEX Summary")
    
    # Create two columns for CAPEX and OPEX
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Capital Expenditure (CAPEX)")
        
        # Display metrics for each CAPEX item in PHP
        for item, cost in capex_items.items():
            php_cost = cost * php_conversion_rate
            st.metric(item, f"₱{php_cost:,.2f}", f"{cost/design_values['total_capex']*100:.1f}%")
        
        php_total_capex = design_values['total_capex'] * php_conversion_rate
        st.metric("Total CAPEX", f"₱{php_total_capex:,.2f}", f"(${design_values['total_capex']:,.2f} USD)")
        
        # CAPEX visualization
        st.write("### CAPEX Breakdown")
        capex_df = pd.DataFrame({
            'Component': list(capex_items.keys()),
            'Cost (PHP)': [cost * php_conversion_rate for cost in capex_items.values()]
        })
        st.bar_chart(capex_df.set_index('Component'))
    
    with col2:
        st.subheader("Operational Expenditure (OPEX)")
        
        # Display metrics for each OPEX item in PHP
        for item, cost in opex_items.items():
            php_cost = cost * php_conversion_rate
            st.metric(item, f"₱{php_cost:,.2f}", f"{cost/design_values['total_monthly_opex']*100:.1f}%")
        
        php_total_monthly_opex = design_values['total_monthly_opex'] * php_conversion_rate
        st.metric("Total Monthly OPEX", f"₱{php_total_monthly_opex:,.2f}", f"(${design_values['total_monthly_opex']:,.2f} USD)")
        php_annual_opex = design_values['total_monthly_opex'] * 12 * php_conversion_rate
        st.metric("Estimated Annual OPEX", f"₱{php_annual_opex:,.2f}", f"(${design_values['total_monthly_opex']*12:,.2f} USD)")
        
        # OPEX visualization
        st.write("### Monthly OPEX Breakdown")
        opex_df = pd.DataFrame({
            'Component': list(opex_items.keys()),
            'Cost (PHP)': [cost * php_conversion_rate for cost in opex_items.values()]
        })
        st.bar_chart(opex_df.set_index('Component'))
    
    # Financial analysis section
    st.subheader("Financial Analysis")
    
    # Simple payback and ROI analysis
    years_of_operation = st.slider("Years of Operation", min_value=1, max_value=20, value=10)
    annual_opex = design_values['total_monthly_opex'] * 12
    total_opex_over_lifetime = annual_opex * years_of_operation
    total_cost_over_lifetime = design_values['total_capex'] * 1.232 + total_opex_over_lifetime
    
    # Convert to PHP
    php_annual_opex = annual_opex * php_conversion_rate
    php_total_opex_over_lifetime = total_opex_over_lifetime * php_conversion_rate
    php_total_cost_over_lifetime = total_cost_over_lifetime * php_conversion_rate
    
    st.header("Expenditure Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Cost of Sales", f"₱{php_total_capex:,.2f}", f"(${design_values['total_capex']:,.2f} USD)")
    with col2:
        st.metric(f"Total OPEX ({years_of_operation} years)", f"₱{php_total_opex_over_lifetime:,.2f}", f"(${total_opex_over_lifetime:,.2f} USD)")
    with col3:
        st.metric(f"Total Expenditure (TotEx) ({years_of_operation} years)", f"₱{php_total_cost_over_lifetime:,.2f}", f"(${total_cost_over_lifetime:,.2f} USD)")
        
    st.header("Margin Analysis")
    col7, col8, col9 = st.columns(3)
    
    with col7:
        st.metric("EPC Margin", f"₱{design_values['epc_cost'] * php_conversion_rate:,.2f}", f"(${design_values['total_capex'] * 0.1:,.2f} USD)")
    with col8:
        st.metric("Contingency", f"₱{php_total_capex * 0.1:,.2f}", f"(${design_values['total_capex'] * 0.1:,.2f} USD)")
    with col9:
        st.metric("EPC + Contingency", f"₱{design_values['epc_cost'] * php_conversion_rate + php_total_capex * 0.1:,.2f}", f"(${design_values['total_capex'] * 1.1 * 0.12:.2f} USD)")
    
    st.header("Bid Price Analysis")
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.metric("Tax", f"₱{php_total_capex * 1.1 * 0.12:,.2f}", f"(${design_values['total_capex'] * 1.1 * 0.12:,.2f} USD)")
    with col6:
        st.metric("Total Bid Price + Tax & Contingency", f"₱{php_total_capex + php_total_capex * 1.1 * 0.12 + php_total_capex * 0.1:,.2f}", f"(${design_values['total_capex']:,.2f} USD)")
        
    
    # Calculate cost per cubic meter treated
    total_volume_treated = design_values['flowrate'] * 365 * years_of_operation
    cost_per_cubic_meter = total_cost_over_lifetime / total_volume_treated
    php_cost_per_cubic_meter = cost_per_cubic_meter * php_conversion_rate
    
    st.header("OpEx Analysis")
    col10, col11, col12 = st.columns(3)
    with col10:
        st.metric("ToTEx-based Cost Per Cubic Meter Treated", f"₱{php_cost_per_cubic_meter:.2f}/m³", f"(${cost_per_cubic_meter:.2f}/m³ of wastewater)")
    with col11:
        st.metric("ToTEx-based Cost Per Liter Treated", f"₱{php_cost_per_cubic_meter / 1000:.2f}/L", f"(${cost_per_cubic_meter:.2f}/m³ of wastewater)")
    with col12:
        st.metric("OpEx-based Cost Per Liter Treated", f"₱{php_annual_opex / 365 / flowrate / 1000:.2f}/L", f"(${php_annual_opex / 365 / flowrate / php_conversion_rate:.2f}/m³ of wastewater)")
    
    st.subheader("Cost Assumptions")
    
    # Create a two-column layout for assumptions
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Unit Costs")
        st.write(f"- AOP Reactor: ${aop_reactor_unit_cost:.2f} per reactor")
        st.write(f"- Ozone Generator: ${ozone_generator_unit_cost:.2f} per unit")
        st.write(f"- Pump: ${pump_unit_cost:.2f} per pump")
        st.write(f"- Sand Filtration: ${filter_unit_cost:.2f} per filter unit")
        st.write(f"- Electricity Cost: {design_values['electricity_cost'] * php_conversion_rate:.2f} Pesos per kWh")
        st.write(f"- Chemical Cost Factor: {design_values['chemical_cost_factor']:.1f}")
        
    with col2:
        st.write("### Operational Parameters")
        st.write(f"- Ozone Power: {ozone_power_consumption:.1f} kWh per kg O₃")
        st.write(f"- Pumping Power: {pump_power_consumption:.2f} kWh per m³")
        st.write(f"- Chemical Cost: {chemicals_base_cost * php_conversion_rate:.2f} Pesos per m³ treated")
        st.write(f"- Operators Required: {design_values['operators_required']}")
        st.write(f"- Operator Salary: {operator_monthly_salary * php_conversion_rate:,.2f} Pesos per operator per month")
        st.write(f"- Maintenance: {maintenance_factor:.1f}% of CAPEX per year")
    
    # Download detailed cost breakdown
    st.subheader("Download Detailed Cost Analysis")
    
    # Create detailed cost DataFrame
    detailed_cost_data = {
        "Component": list(capex_items.keys()) + ["Total CAPEX"] + list(opex_items.keys()) + ["Total Monthly OPEX", "Annual OPEX", f"Lifetime OPEX ({years_of_operation} years)", f"Total Lifetime Cost ({years_of_operation} years)", "Cost Per Cubic Meter"],
        "Cost (PHP)": [value * php_conversion_rate for value in capex_items.values()] + [design_values['total_capex'] * php_conversion_rate] + [value * php_conversion_rate for value in opex_items.values()] + [design_values['total_monthly_opex'] * php_conversion_rate, annual_opex * php_conversion_rate, total_opex_over_lifetime * php_conversion_rate, total_cost_over_lifetime * php_conversion_rate, cost_per_cubic_meter * php_conversion_rate],
        "Category": ["CAPEX"]*len(capex_items) + ["CAPEX"] + ["Monthly OPEX"]*len(opex_items) + ["Monthly OPEX", "Annual OPEX", "Lifetime OPEX", "Total Cost", "Unit Cost"]
    }
    
    # Create notes list with the correct length
    notes = []
    # Add notes for CAPEX items
    notes.extend(["AOP reactor cost", "Ozone generator cost", "Pumping equipment cost", 
                 "Sand filtration system", "pH adjustment system", "Container Housing", 
                 "Piping and instrumentation", "Engineering, procurement, and construction"])
    # Add note for Total CAPEX
    notes.append("Total capital expenditure")
    # Add notes for OPEX items
    notes.extend(["Power for ozone generation", "Power for pumping", "Chemical costs for pH adjustment", 
                 "Staff costs", "Parts and consumables"])
    # Add remaining notes
    notes.extend(["Total monthly operational cost", "Annual operational cost", 
                f"Operational cost over {years_of_operation} years", 
                f"Total cost over {years_of_operation} years", 
                "Cost per cubic meter of water treated"])
    
    # Add notes to the dictionary
    detailed_cost_data["Notes"] = notes
    
    # Now create the DataFrame
    detailed_cost_df = pd.DataFrame(detailed_cost_data)
    
    # Prepare CSV download
    cost_csv = convert_df_to_csv(detailed_cost_df)
    
    st.download_button(
        label="Download Detailed Cost Analysis as CSV",
        data=cost_csv,
        file_name="wastewater_treatment_cost_analysis.csv",
        mime="text/csv",
    )

# Add a footer
st.markdown("---")
st.markdown("© 2025 ECH2O Advanced Oxidation Process Design Dashboard | Created: April 2025")