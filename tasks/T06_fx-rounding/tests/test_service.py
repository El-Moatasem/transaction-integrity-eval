import pytest
from service import convert

def test_half_even_tie_and_jpy():
    assert convert('1.01','USD','USD','0.5')=={'target_minor':50,'target_amount':'0.50','rate':'0.5'}
    assert convert('1.00','USD','JPY','100.5')=={'target_minor':100,'target_amount':'100','rate':'100.5'}
    assert convert('1.00','USD','JPY','101.5')['target_minor']==102

def test_scale_three_and_exact_source_minor():
    assert convert('1.00','USD','KWD','0.3335')=={'target_minor':334,'target_amount':'0.334','rate':'0.3335'}
    assert convert('10','JPY','USD','0.0125')['target_amount']=='0.12'
    assert convert('1.2000','USD','USD','1')['target_minor']==120

def test_reject_invalid_inputs():
    cases=[('1.001','USD','EUR','1'),('1.1','JPY','USD','1'),('0','USD','EUR','1'),('1','USD','EUR','0'),('1','USD','BAD','1'),('1','USD','EUR','NaN'),(1.2,'USD','EUR','1'),('1','USD','EUR',1.2),('Infinity','USD','EUR','1')]
    for case in cases:
        with pytest.raises(ValueError):convert(*case)
