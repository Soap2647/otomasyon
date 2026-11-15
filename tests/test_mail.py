from otomasyon.mail import maskele


def test_otp_konuda_once_gelen_kod():
    assert maskele("095350 is your X verification code") == "[kod] is your X verification code"


def test_otp_turkce():
    assert maskele("Google doğrulama kodunuz: 482913") == "Google doğrulama kodunuz: [kod]"


def test_normal_sayilar_korunur():
    assert maskele("Re: 949484 ID'li MTKB Projesinin İptali") == "Re: 949484 ID'li MTKB Projesinin İptali"


def test_link_maskelenir():
    assert maskele("bkz https://ornek.com/a?b=1 lütfen") == "bkz [link] lütfen"
