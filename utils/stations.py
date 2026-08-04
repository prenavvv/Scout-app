"""
Hardcoded coordinates of major Indian Railway stations.

This is intentionally a curated shortlist (not exhaustive) of major/junction
stations, since the scorer only needs to know "is this attraction close to
SOME train-accessible hub", not every single halt station in India.

Format: "Station Name (CODE)": (latitude, longitude)

Add more stations here anytime -- the rest of the code just imports this dict.
"""

STATIONS = {
    "Ernakulam Junction (ERS)": (9.9816, 76.2999),
    "Kochi Harbour Terminus (CHTS)": (9.9500, 76.2600),
    "Thiruvananthapuram Central (TVC)": (8.4875, 76.9525),
    "Kozhikode (CLT)": (11.2497, 75.7804),
    "Thrissur (TCR)": (10.5276, 76.2144),
    "Kollam Junction (QLN)": (8.8932, 76.6141),
    "Kannur (CAN)": (11.8689, 75.3567),
    "Chennai Central (MAS)": (13.0827, 80.2750),
    "Chennai Egmore (MS)": (13.0732, 80.2609),
    "Coimbatore Junction (CBE)": (11.0018, 76.9629),
    "Madurai Junction (MDU)": (9.9195, 78.1193),
    "Trichy Junction (TPJ)": (10.8155, 78.6866),
    "Bengaluru City Junction (SBC)": (12.9767, 77.5713),
    "Mysuru Junction (MYS)": (12.3151, 76.6551),
    "Mangaluru Central (MAQ)": (12.8698, 74.8425),
    "Hyderabad Deccan (HYB)": (17.3833, 78.4867),
    "Secunderabad Junction (SC)": (17.4344, 78.5015),
    "Vijayawada Junction (BZA)": (16.5175, 80.6224),
    "Visakhapatnam (VSKP)": (17.7167, 83.2185),
    "Tirupati (TPTY)": (13.6333, 79.4167),
    "Mumbai CST (CSMT)": (18.9398, 72.8355),
    "Mumbai Central (BCT)": (18.9695, 72.8194),
    "Pune Junction (PUNE)": (18.5286, 73.8744),
    "Nagpur (NGP)": (21.1524, 79.0882),
    "Ahmedabad Junction (ADI)": (23.0258, 72.6011),
    "Surat (ST)": (21.1959, 72.8302),
    "Jaipur Junction (JP)": (26.9196, 75.7877),
    "Udaipur City (UDZ)": (24.5854, 73.6842),
    "Jodhpur Junction (JU)": (26.2870, 73.0243),
    "Delhi Junction (DLI)": (28.6600, 77.2273),
    "New Delhi (NDLS)": (28.6431, 77.2197),
    "Agra Cantt (AGC)": (27.1560, 78.0089),
    "Varanasi Junction (BSB)": (25.3287, 82.9878),
    "Lucknow Charbagh (LKO)": (26.8302, 80.9214),
    "Patna Junction (PNBE)": (25.6100, 85.1416),
    "Kolkata (Howrah) (HWH)": (22.5839, 88.3425),
    "Kolkata (Sealdah) (SDAH)": (22.5675, 88.3707),
    "Bhubaneswar (BBS)": (20.2660, 85.8318),
    "Puri (PURI)": (19.8074, 85.8312),
    "Guwahati (GHY)": (26.1795, 91.7532),
    "Amritsar Junction (ASR)": (31.6340, 74.8723),
    "Chandigarh (CDG)": (30.7343, 76.8129),
    "Bhopal Junction (BPL)": (23.2681, 77.4013),
    "Indore Junction (INDB)": (22.7167, 75.8472),
    "Gwalior (GWL)": (26.2124, 78.1772),
    "Dwarka (DWK)": (22.2394, 68.9678),
    "Somnath (SMNH)": (20.8880, 70.4013),
    "Shirdi (SNSI)": (19.8410, 74.4770),
    "Rameswaram (RMM)": (9.2833, 79.3167),
    "Kanyakumari (CAPE)": (8.0778, 77.5432),
    "Jammu Tawi (JAT)": (32.6926, 74.8580),
    "Katra (SVDK)": (32.9916, 74.9310),
}
